/// 通用错误响应模型
/// 兼容两种后端错误格式：
/// 1. 直接格式：{ "error": { "code": "...", "message": "..." } }
/// 2. FastAPI 包装格式：{ "detail": { "error": { "code": "...", "message": "..." } } }
class ErrorResponse {
  final String code;
  final String message;

  const ErrorResponse({required this.code, required this.message});

  factory ErrorResponse.fromJson(Map<String, dynamic> json) {
    // 格式 1：直接 { "error": {...} }
    Map<String, dynamic>? error = json['error'] as Map<String, dynamic>?;

    // 格式 2：FastAPI 包装 { "detail": { "error": {...} } }
    if (error == null) {
      final detail = json['detail'];
      if (detail is Map<String, dynamic>) {
        error = detail['error'] as Map<String, dynamic>?;
        // detail 本身可能就是错误对象
        if (error == null && (detail.containsKey('code') || detail.containsKey('message'))) {
          error = detail;
        }
      }
    }

    return ErrorResponse(
      code: error?['code'] as String? ?? 'UNKNOWN',
      message: error?['message'] as String? ?? '未知错误',
    );
  }
}

/// API 异常，用于 services 层抛出
class ApiException implements Exception {
  final String code;
  final String message;
  final int? statusCode;

  const ApiException({
    required this.code,
    required this.message,
    this.statusCode,
  });

  @override
  String toString() => message;
}
