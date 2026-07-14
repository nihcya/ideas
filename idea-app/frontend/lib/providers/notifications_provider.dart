import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/notification.dart';
import 'api_provider.dart';

/// 通知列表 Notifier — 管理通知列表 + 未读数
class NotificationsNotifier extends AsyncNotifier<NotificationList> {
  @override
  Future<NotificationList> build() async {
    final notificationService = ref.read(notificationServiceProvider);
    return notificationService.getNotifications();
  }

  /// 刷新通知列表
  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(notificationServiceProvider).getNotifications());
  }

  /// 标记通知为已读
  Future<void> markRead(List<String> notificationIds) async {
    final notificationService = ref.read(notificationServiceProvider);
    await notificationService.markRead(notificationIds);
    await refresh();
  }
}

/// 通知列表 Provider
final notificationsProvider =
    AsyncNotifierProvider<NotificationsNotifier, NotificationList>(
        NotificationsNotifier.new);
