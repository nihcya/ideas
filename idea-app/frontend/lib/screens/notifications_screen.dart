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
    if (context.mounted && n.ideaId != null) {
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
