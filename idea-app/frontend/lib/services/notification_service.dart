import 'package:dio/dio.dart';

import '../models/notification.dart';
import 'api_client.dart';

/// 通知服务：获取通知列表 / 标记已读
class NotificationService {
  final Dio _dio;

  NotificationService(this._dio);

  /// 获取通知列表
  Future<NotificationList> getNotifications({
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final res = await _dio.get('/notifications', queryParameters: {
        'limit': limit,
        'offset': offset,
      });
      return NotificationList.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 读取和更新通知偏好\n
  Future<List<NotificationPreferenceItem>> getPreferences() async {
    try {
      final res = await _dio.get('/notifications/preferences');
      final items = (res.data as Map<String, dynamic>)['items'] as List<dynamic>? ?? [];
      return items
          .map((item) => NotificationPreferenceItem.fromJson(
                Map<String, dynamic>.from(item as Map),
              ))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  Future<List<NotificationPreferenceItem>> updatePreferences(
    List<NotificationPreferenceItem> items,
  ) async {
    try {
      final res = await _dio.put('/notifications/preferences', data: {
        'items': items.map((item) => item.toJson()).toList(),
      });
      final values = (res.data as Map<String, dynamic>)['items'] as List<dynamic>? ?? [];
      return values
          .map((item) => NotificationPreferenceItem.fromJson(
                Map<String, dynamic>.from(item as Map),
              ))
          .toList();
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
\n  /// 标记通知为已读
  /// [notificationIds] 需要标记已读的通知 ID 列表
  Future<int> markRead(List<String> notificationIds) async {
    try {
      final res = await _dio.post('/notifications/read', data: {
        'notification_ids': notificationIds,
      });
      final data = res.data as Map<String, dynamic>;
      return data['marked_read'] as int? ?? 0;
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
}
