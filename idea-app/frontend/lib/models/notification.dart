/// 通知类型
typedef NotificationType = String; // forked | collected | spark_updated

/// 通知项
class NotificationItem {
  final String id;
  final String type;
  final String content;
  final String? ideaId;
  final String? actorId;
  final DateTime createdAt;
  final bool read;

  const NotificationItem({
    required this.id,
    required this.type,
    required this.content,
    this.ideaId,
    this.actorId,
    required this.createdAt,
    required this.read,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    return NotificationItem(
      id: json['id'] as String,
      type: json['type'] as String,
      content: json['content'] as String,
      ideaId: json['idea_id'] as String?,
      actorId: json['actor_id'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      read: json['read'] as bool? ?? false,
    );
  }
}

/// 通知列表响应
class NotificationList {
  final List<NotificationItem> notifications;
  final int unreadCount;

  const NotificationList({
    required this.notifications,
    required this.unreadCount,
  });

  factory NotificationList.fromJson(Map<String, dynamic> json) {
    return NotificationList(
      notifications: ((json['notifications'] as List<dynamic>?) ?? [])
          .map((e) => NotificationItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      unreadCount: json['unread_count'] as int? ?? 0,
    );
  }
}
