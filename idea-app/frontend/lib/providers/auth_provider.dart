import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user.dart';
import '../services/api_client.dart';
import '../services/storage_service.dart';
import 'api_provider.dart';

/// 认证状态 sealed class
///
/// router 通过 `authStateProvider` watch 此状态，并调用 `maybeWhen` 判断是否已登录。
/// `maybeWhen(authenticated: (_) => true, orElse: () => false)` 必须能正常工作。
sealed class AuthState {
  const AuthState();

  R maybeWhen<R>({
    R Function(UserBrief user)? authenticated,
    R Function()? unauthenticated,
    R Function()? loading,
    required R Function() orElse,
  });
}

/// 加载中（启动时检查 token）
class AuthLoading extends AuthState {
  const AuthLoading();

  @override
  R maybeWhen<R>({
    R Function(UserBrief user)? authenticated,
    R Function()? unauthenticated,
    R Function()? loading,
    required R Function() orElse,
  }) {
    return loading?.call() ?? orElse();
  }
}

/// 已登录
class Authenticated extends AuthState {
  final UserBrief user;
  const Authenticated(this.user);

  @override
  R maybeWhen<R>({
    R Function(UserBrief user)? authenticated,
    R Function()? unauthenticated,
    R Function()? loading,
    required R Function() orElse,
  }) {
    return authenticated?.call(user) ?? orElse();
  }
}

/// 未登录
class Unauthenticated extends AuthState {
  const Unauthenticated();

  @override
  R maybeWhen<R>({
    R Function(UserBrief user)? authenticated,
    R Function()? unauthenticated,
    R Function()? loading,
    required R Function() orElse,
  }) {
    return unauthenticated?.call() ?? orElse();
  }
}

/// 认证状态管理 Notifier
///
/// 启动时从 FlutterSecureStorage 读取已存储的 token / user 信息，
/// 决定初始状态为 Authenticated 或 Unauthenticated。
/// 401 时由 apiClient 拦截器调用 setUnauthenticated()。
class AuthNotifier extends Notifier<AuthState> {
  @override
  AuthState build() {
    _init();
    return const AuthLoading();
  }

  /// 异步初始化：检查本地存储的认证信息
  Future<void> _init() async {
    final storage = StorageService();
    final token = await storage.read(key: kTokenKey);
    final userId = await storage.read(key: kUserIdKey);
    final username = await storage.read(key: kUsernameKey);

    if (token != null &&
        token.isNotEmpty &&
        userId != null &&
        username != null) {
      state = Authenticated(UserBrief(id: userId, username: username));
    } else {
      state = const Unauthenticated();
    }
  }

  /// 设置为已登录状态
  void setAuthenticated(UserBrief user) {
    state = Authenticated(user);
  }

  /// 设置为未登录状态（登出 / 401 时调用）
  void setUnauthenticated() {
    state = const Unauthenticated();
  }
}

/// 认证状态 Provider
///
/// router 使用方式：
/// ```dart
/// final authState = ref.watch(authStateProvider);
/// final isLoggedIn = authState.maybeWhen(
///   authenticated: (_) => true,
///   orElse: () => false,
/// );
/// ```
final authStateProvider =
    NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);

// ============================================================
// Action Providers — 供 UI 调用的登录/注册/登出操作
// ============================================================

/// 登录 action
/// 用法：`await ref.read(loginActionProvider)(username, password)`
final loginActionProvider =
    Provider<Future<AuthResult> Function(String username, String password)>(
        (ref) {
  return (String username, String password) async {
    final authService = ref.read(authServiceProvider);
    final result = await authService.login(
      username: username,
      password: password,
    );
    ref.read(authStateProvider.notifier).setAuthenticated(
          UserBrief(id: result.userId, username: result.username),
        );
    return result;
  };
});

/// 注册 action
/// 用法：`await ref.read(registerActionProvider)(username: ..., password: ..., bio: ...)`
final registerActionProvider =
    Provider<Future<AuthResult> Function({
  required String username,
  required String password,
  String bio,
})>((ref) {
  return ({
    required String username,
    required String password,
    String bio = '',
  }) async {
    final authService = ref.read(authServiceProvider);
    final result = await authService.register(
      username: username,
      password: password,
      bio: bio,
    );
    ref.read(authStateProvider.notifier).setAuthenticated(
          UserBrief(id: result.userId, username: result.username),
        );
    return result;
  };
});

/// 登出 action
/// 用法：`await ref.read(logoutActionProvider)()`
final logoutActionProvider = Provider<Future<void> Function()>((ref) {
  return () async {
    final authService = ref.read(authServiceProvider);
    await authService.logout();
    ref.read(authStateProvider.notifier).setUnauthenticated();
  };
});
