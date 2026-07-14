import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../models/user.dart';
import 'api_client.dart';
import 'storage_service.dart';

/// 认证服务：注册 / 登录 / 登出 / Token 管理
class AuthService {
  final Dio _dio;
  final StorageService _storage;

  AuthService(this._dio, [StorageService? storage])
      : _storage = storage ?? StorageService();

  /// 注册新用户
  Future<AuthResult> register({
    required String username,
    required String password,
    String bio = '',
  }) async {
    try {
      final res = await _dio.post('/auth/register', data: {
        'username': username,
        'password': password,
        'bio': bio,
      });
      final result = _parseAuthResult(res.data);
      await _saveAuth(result);
      return result;
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 登录
  Future<AuthResult> login({
    required String username,
    required String password,
  }) async {
    try {
      final res = await _dio.post('/auth/login', data: {
        'username': username,
        'password': password,
      });
      final result = _parseAuthResult(res.data);
      await _saveAuth(result);
      return result;
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 解析后端认证响应，兼容 Map 和 JSON 字符串两种格式
  AuthResult _parseAuthResult(dynamic data) {
    Map<String, dynamic> json;
    if (data is Map<String, dynamic>) {
      json = data;
    } else if (data is String) {
      json = jsonDecode(data) as Map<String, dynamic>;
    } else {
      throw FormatException('意外的响应格式: ${data.runtimeType}');
    }
    debugPrint('Auth response parsed: userId=${json['user_id']}, username=${json['username']}');
    return AuthResult.fromJson(json);
  }

  /// 登出：清除本地存储
  Future<void> logout() async {
    await _storage.delete(key: kTokenKey);
    await _storage.delete(key: kUserIdKey);
    await _storage.delete(key: kUsernameKey);
  }

  /// 读取已存储的 token
  Future<String?> getToken() async {
    return await _storage.read(key: kTokenKey);
  }

  /// 读取已存储的用户 ID
  Future<String?> getUserId() async {
    return await _storage.read(key: kUserIdKey);
  }

  /// 读取已存储的用户名
  Future<String?> getUsername() async {
    return await _storage.read(key: kUsernameKey);
  }

  /// 保存认证信息到本地存储
  Future<void> _saveAuth(AuthResult result) async {
    await _storage.write(key: kTokenKey, value: result.token);
    await _storage.write(key: kUserIdKey, value: result.userId);
    await _storage.write(key: kUsernameKey, value: result.username);
  }

  /// 检查是否已登录（token 是否存在）
  Future<bool> isAuthenticated() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }

  /// 获取当前登录用户的简要信息（从本地存储）
  Future<UserBrief?> getCurrentUser() async {
    final id = await getUserId();
    final username = await getUsername();
    if (id == null || username == null) return null;
    return UserBrief(id: id, username: username);
  }
}
