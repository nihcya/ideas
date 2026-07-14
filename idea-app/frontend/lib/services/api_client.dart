import 'package:dio/dio.dart';

import '../models/api_response.dart';
import 'storage_service.dart';

/// API 基础 URL
///
/// 通过 `--dart-define=API_BASE_URL=...` 编译时注入，实现多环境支持。
/// - 开发环境（默认）：http://127.0.0.1:8765/api（本地后端）
/// - 生产环境：构建时传入 --dart-define=API_BASE_URL=http://124.221.108.59/api
///
/// 端口 8765：避开 Windows Hyper-V/WSL 的 8000 端口保留范围（WinError 10013）。
const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://127.0.0.1:8765/api',
);

/// Storage keys
const String kTokenKey = 'jwt_token';
const String kUserIdKey = 'user_id';
const String kUsernameKey = 'username';

/// 创建配置好的 Dio 实例
///
/// [onUnauthorized] 在收到 401 响应时被调用，用于清除登录状态并跳转登录页。
Dio createApiClient({required void Function() onUnauthorized}) {
  final dio = Dio(BaseOptions(
    baseUrl: kApiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    headers: {'Content-Type': 'application/json'},
  ));

  final storage = StorageService();

  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) async {
      final token = await storage.read(key: kTokenKey);
      if (token != null && token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    },
    onError: (e, handler) async {
      if (e.response?.statusCode == 401) {
        // 清除本地存储的认证信息
        await storage.delete(key: kTokenKey);
        await storage.delete(key: kUserIdKey);
        await storage.delete(key: kUsernameKey);
        // 通知上层更新认证状态（会触发路由跳转到 /auth）
        onUnauthorized();
      }
      handler.next(e);
    },
  ));

  return dio;
}

/// 从响应 data 中提取 error 对象，兼容两种格式：
/// 1. 直接格式：{ "error": { "code": "...", "message": "..." } }
/// 2. FastAPI HTTPException 包装格式：{ "detail": { "error": { "code": "...", "message": "..." } } }
/// 3. FastAPI Pydantic 校验错误：{ "detail": [ { "msg": "..." } ] }
/// 4. 简单字符串格式：{ "detail": "错误信息" }
Map<String, dynamic>? _extractErrorObject(dynamic data) {
  if (data is! Map<String, dynamic>) return null;

  // 格式 1：直接 { "error": {...} }
  final error = data['error'];
  if (error is Map<String, dynamic>) return error;

  // 格式 2：FastAPI 包装 { "detail": { "error": {...} } }
  final detail = data['detail'];
  if (detail is Map<String, dynamic>) {
    final nestedError = detail['error'];
    if (nestedError is Map<String, dynamic>) return nestedError;
    // detail 本身就是错误对象（无 error 嵌套）
    if (detail.containsKey('code') || detail.containsKey('message')) {
      return detail;
    }
  }

  return null;
}

/// 从 Pydantic 校验错误（detail 是数组）中提取第一条消息
String? _extractPydanticError(Map<String, dynamic> data) {
  final detail = data['detail'];
  if (detail is List && detail.isNotEmpty) {
    final first = detail.first;
    if (first is Map<String, dynamic>) {
      final msg = first['msg'] as String?;
      final loc = first['loc'] as List?;
      if (msg != null) {
        // loc 示例：["body", "password"] → 提取字段名
        final field = loc != null && loc.length >= 2 ? loc.last : null;
        return field != null ? '$field: $msg' : msg;
      }
    }
  }
  return null;
}

/// 从 DioException 提取后端错误信息
/// 兼容后端多种错误格式
String extractErrorMessage(DioException e) {
  final data = e.response?.data;
  if (data is Map<String, dynamic>) {
    // 尝试提取 error 对象
    final errorObj = _extractErrorObject(data);
    if (errorObj != null) {
      return errorObj['message'] as String? ?? '未知错误';
    }

    // 尝试 Pydantic 校验错误
    final pydanticMsg = _extractPydanticError(data);
    if (pydanticMsg != null) return pydanticMsg;

    // 尝试直接 message 字段
    final msg = data['message'] as String?;
    if (msg != null) return msg;

    // detail 是简单字符串
    final detail = data['detail'];
    if (detail is String) return detail;
  }

  // 网络错误
  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
      return '网络连接超时，请检查网络';
    case DioExceptionType.connectionError:
      return '无法连接服务器，请检查网络';
    case DioExceptionType.cancel:
      return '请求已取消';
    default:
      return '网络错误';
  }
}

/// 将 DioException 转换为 ApiException
ApiException toApiException(DioException e) {
  final data = e.response?.data;
  String code = 'UNKNOWN';
  String message = extractErrorMessage(e);

  if (data is Map<String, dynamic>) {
    final errorObj = _extractErrorObject(data);
    if (errorObj != null) {
      code = errorObj['code'] as String? ?? 'UNKNOWN';
      message = errorObj['message'] as String? ?? message;
    } else if (data['detail'] is List) {
      // Pydantic 校验错误
      code = 'VALIDATION_ERROR';
    }
  }

  return ApiException(
    code: code,
    message: message,
    statusCode: e.response?.statusCode,
  );
}
