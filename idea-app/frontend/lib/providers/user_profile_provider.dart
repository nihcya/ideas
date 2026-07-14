import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user.dart';
import 'api_provider.dart';

/// 用户主页 Notifier — family，按 userId 获取公开主页（思维森林）
class UserProfileNotifier extends FamilyAsyncNotifier<UserProfile, String> {
  @override
  Future<UserProfile> build(String userId) async {
    final userService = ref.read(userServiceProvider);
    return userService.getUserProfile(userId);
  }

  /// 刷新用户主页
  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(userServiceProvider).getUserProfile(arg));
  }
}

/// 用户主页 Provider — family，传入 userId
///
/// 用法：`ref.watch(userProfileProvider(userId))`
final userProfileProvider =
    AsyncNotifierProvider.family<UserProfileNotifier, UserProfile, String>(
        UserProfileNotifier.new);
