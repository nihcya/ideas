import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/notification.dart';
import '../providers/notifications_provider.dart';
import '../theme/app_theme.dart';

/// 通知列表页
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  Future<void> _refresh(WidgetRef ref) async {
    await ref.read(notificationsProvider.notifier).refresh();
  }

  Future<void> _onTap(BuildContext context, WidgetRef ref, NotificationItem n) async {
    if (!n.read) {
      try {
        await ref.read(notificationsProvider.notifier).markRead([n.id]);
      } catch (_) {}
    }
    if (context.mounted && n.collaborationId != null) {
      context.push('/collaborations/${n.collaborationId}');
    } else if (context.mounted && n.ideaId != null) {
      context.push('/idea/${n.ideaId}');
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncList = ref.watch(notificationsProvider);
    final colors = AppColors.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('通知'),
        actions: [
          IconButton(
            tooltip: '通知偏好',
            icon: const Icon(Icons.tune),
            onPressed: () => context.push('/notifications/preferences'),
          ),
          IconButton(
            tooltip: '创意邀请',
            icon: const Icon(Icons.mail_outline),
            onPressed: () => context.push('/invites'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _refresh(ref),
        child: asyncList.when(
          data: (data) {
            if (data.notifications.isEmpty) {
              return ListView(
                children: [
                  const SizedBox(height: 240),
                  Center(
                    child: Text(
                      '暂无通知',
                      style: TextStyle(color: colors.textSecondary),
                    ),
                  ),
                ],
              );
            }
            return ListView.separated(
              itemCount: data.notifications.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final n = data.notifications[i];
                return _NotificationTile(
                  item: n,
                  onTap: () => _onTap(context, ref, n),
                );
              },
            );
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, st) => ListView(
            children: [
              const SizedBox(height: 200),
              Center(child: Text('加载失败：$e')),
              const SizedBox(height: 16),
              Center(
                child: TextButton(
                  onPressed: () => _refresh(ref),
                  child: const Text('重试'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final NotificationItem item;
  final VoidCallback onTap;
  const _NotificationTile({required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colors = AppColors.of(context);
    return InkWell(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          border: Border(
            left: BorderSide(
              color: item.read ? Colors.transparent : colors.gold,
              width: 3,
            ),
          ),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _typeIcon(item.type, colors),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.content,
                    style: TextStyle(
                      fontSize: 14,
                      color:
                          item.read ? colors.textSecondary : colors.textPrimary,
                      fontWeight:
                          item.read ? FontWeight.normal : FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _formatTime(item.createdAt),
                    style: TextStyle(
                      fontSize: 11,
                      color: colors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _typeIcon(String type, AppColors colors) {
    IconData icon;
    Color color;
    switch (type) {
      case 'forked':
        icon = Icons.call_split;
        color = colors.gold;
        break;
      case 'collected':
        icon = Icons.bookmark_border;
        color = colors.success;
        break;
      case 'spark_updated':
        icon = Icons.bolt_outlined;
        color = colors.forkAccent;
        break;
      case 'collab_published':
      case 'collab_invited':
      case 'collab_reviewed':
        icon = Icons.groups_outlined;
        color = colors.gold;
        break;
      default:
        icon = Icons.notifications_outlined;
        color = colors.textSecondary;
    }
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        shape: BoxShape.circle,
      ),
      child: Icon(icon, color: color, size: 18),
    );
  }

  String _formatTime(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes} 分钟前';
    if (diff.inHours < 24) return '${diff.inHours} 小时前';
    if (diff.inDays < 30) return '${diff.inDays} 天前';
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
  }
}



/// 用户可按通知类型启用或关闭站内通知。
class NotificationPreferencesScreen extends ConsumerStatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  ConsumerState<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends ConsumerState<NotificationPreferencesScreen> {
  late Future<List<NotificationPreferenceItem>> _preferences;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _preferences = ref.read(notificationServiceProvider).getPreferences();
  }

  Future<void> _refresh() async {
    setState(() {
      _preferences = ref.read(notificationServiceProvider).getPreferences();
    });
    await _preferences;
  }

  Future<void> _change(
    NotificationPreferenceItem changed,
    bool enabled,
    List<NotificationPreferenceItem> current,
  ) async {
    if (_saving) return;
    final optimistic = current
        .map((item) => item.notificationType == changed.notificationType
            ? item.copyWith(enabled: enabled)
            : item)
        .toList();
    setState(() {
      _saving = true;
      _preferences = Future.value(optimistic);
    });
    try {
      final saved = await ref
          .read(notificationServiceProvider)
          .updatePreferences(optimistic);
      if (mounted) {
        setState(() => _preferences = Future.value(saved));
      }
    } catch (error) {
      if (mounted) {
        setState(() => _preferences = Future.value(current));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('保存通知偏好失败：$error')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String _title(String type) {
    switch (type) {
      case 'forked':
        return '创意被衍生';
      case 'collected':
        return '创意被收藏';
      case 'spark_updated':
        return '灵感动态';
      case 'collab_invited':
        return '协作空间邀请';
      case 'collab_reviewed':
        return '协作贡献审核';
      case 'collab_published':
        return '协作成果发布';
      default:
        return type;
    }
  }

  String _description(String type) {
    switch (type) {
      case 'forked':
        return '有人基于你的公开创意创建了衍生创意';
      case 'collected':
        return '有人收藏了你的创意';
      case 'spark_updated':
        return '你参与的灵感活动有新动态';
      case 'collab_invited':
        return '有人邀请你加入异步协作空间';
      case 'collab_reviewed':
        return '你提交的协作贡献已被审核';
      case 'collab_published':
        return '协作空间已发布最终成果';
      default:
        return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('通知偏好')),
      body: FutureBuilder<List<NotificationPreferenceItem>>(
        future: _preferences,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('加载失败：${snapshot.error}'),
                  TextButton(onPressed: _refresh, child: const Text('重试')),
                ],
              ),
            );
          }
          final items = snapshot.data ?? [];
          return ListView(
            children: [
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text('关闭某类通知后，将不再收到该类型的新通知；历史通知会从列表中隐藏。'),
              ),
              ...items.map((item) => SwitchListTile(
                    title: Text(_title(item.notificationType)),
                    subtitle: Text(_description(item.notificationType)),
                    value: item.enabled,
                    onChanged: _saving
                        ? null
                        : (value) => _change(item, value, items),
                  )),
            ],
          );
        },
      ),
    );
  }
}
