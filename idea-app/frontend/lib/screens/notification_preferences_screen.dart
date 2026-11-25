import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/notification.dart';
import '../providers/api_provider.dart';

class NotificationPreferencesScreen extends ConsumerStatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  ConsumerState<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends ConsumerState<NotificationPreferencesScreen> {
  List<NotificationPreferenceItem> _items = [];
  bool _loading = true;
  final Set<String> _saving = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await ref.read(notificationServiceProvider).getPreferences();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('读取通知偏好失败：$error')),
      );
    }
  }

  String _title(String type) {
    switch (type) {
      case 'forked':
        return '创意被衍生';
      case 'collab_published':
        return '协作成果发布';
      case 'collected':
        return '创意被收藏';
      case 'spark_updated':
        return '灵感动态';
      default:
        return type;
    }
  }

  String _description(String type) {
    switch (type) {
      case 'forked':
        return '有人基于你的公开创意创建了衍生作品';
      case 'collab_published':
        return '你参与的协作空间发布了最终成果';
      case 'collected':
        return '其他用户收藏了你的创意';
      case 'spark_updated':
        return '与你相关的灵感动态发生变化';
      default:
        return '控制是否接收此类站内通知';
    }
  }

  Future<void> _toggle(NotificationPreferenceItem item, bool enabled) async {
    setState(() => _saving.add(item.notificationType));
    final proposed = _items
        .map((value) => value.notificationType == item.notificationType
            ? value.copyWith(enabled: enabled)
            : value)
        .toList();
    try {
      final saved = await ref
          .read(notificationServiceProvider)
          .updatePreferences(proposed);
      if (!mounted) return;
      setState(() => _items = saved);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('保存通知偏好失败：$error')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving.remove(item.notificationType));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('通知偏好')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? Center(
                  child: TextButton(onPressed: _load, child: const Text('重新加载')),
                )
              : ListView(
                  children: [
                    const Padding(
                      padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
                      child: Text('选择你希望接收的站内通知类型。关闭后只影响后续新通知，不会删除已有通知。'),
                    ),
                    for (final item in _items)
                      SwitchListTile(
                        value: item.enabled,
                        onChanged: _saving.contains(item.notificationType)
                            ? null
                            : (value) => _toggle(item, value),
                        title: Text(_title(item.notificationType)),
                        subtitle: Text(_description(item.notificationType)),
                        secondary: _saving.contains(item.notificationType)
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.notifications_outlined),
                      ),
                  ],
                ),
    );
  }
}
