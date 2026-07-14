import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/evolve_service.dart';
import '../services/idea_service.dart';
import '../services/notification_service.dart';
import '../services/settings_service.dart';
import '../services/spark_service.dart';
import '../services/user_service.dart';
import '../services/vault_service.dart';
import 'auth_provider.dart';

/// Dio 实例 Provider
///
/// 请求拦截器：自动从 FlutterSecureStorage 读取 JWT token 并添加到 header
/// 响应拦截器：401 时清除 token 并通过 authStateProvider 触发登出 + 路由跳转
final apiClientProvider = Provider<Dio>((ref) {
  return createApiClient(
    onUnauthorized: () {
      // 401 时更新认证状态为未登录
      // router 监听 authStateProvider，状态变化后会自动 redirect 到 /auth
      ref.read(authStateProvider.notifier).setUnauthenticated();
    },
  );
});

/// 认证服务
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref.read(apiClientProvider));
});

/// 点子服务
final ideaServiceProvider = Provider<IdeaService>((ref) {
  return IdeaService(ref.read(apiClientProvider));
});

/// 演化服务（碰撞 + 演化）
final evolveServiceProvider = Provider<EvolveService>((ref) {
  return EvolveService(ref.read(apiClientProvider));
});

/// 仓库服务
final vaultServiceProvider = Provider<VaultService>((ref) {
  return VaultService(ref.read(apiClientProvider));
});

/// 今日一点服务
final sparkServiceProvider = Provider<SparkService>((ref) {
  return SparkService(ref.read(apiClientProvider));
});

/// 用户服务
final userServiceProvider = Provider<UserService>((ref) {
  return UserService(ref.read(apiClientProvider));
});

/// 通知服务
final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService(ref.read(apiClientProvider));
});

/// 设置服务
final settingsServiceProvider = Provider<SettingsService>((ref) {
  return SettingsService(ref.read(apiClientProvider));
});
