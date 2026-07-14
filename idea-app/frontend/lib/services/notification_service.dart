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

  /// 标记通知为已读
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
