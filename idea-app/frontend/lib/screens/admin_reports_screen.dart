import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/api_provider.dart';

/// Admin-only report queue. Server-side allowlist is authoritative.
class AdminReportsScreen extends ConsumerStatefulWidget {
  const AdminReportsScreen({super.key});

  @override
  ConsumerState<AdminReportsScreen> createState() => _AdminReportsScreenState();
}

class _AdminReportsScreenState extends ConsumerState<AdminReportsScreen> {
  String _status = 'pending';
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await ref.read(ideaServiceProvider).getAdminReports(status: _status);
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  String _reason(String value) {
    switch (value) {
      case 'spam':
        return '垃圾或广告';
      case 'harassment':
        return '骚扰或仇恨';
      case 'copyright':
        return '著作权';
      case 'privacy':
        return '隐私泄露';
      case 'misinformation':
        return '虚假信息';
      default:
        return '其他';
    }
  }

  Future<void> _review(Map<String, dynamic> report) async {
    final noteController = TextEditingController();
    var decision = 'in_review';
    var hideIdea = false;
    final payload = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('处理举报'),
          content: SizedBox(
            width: 440,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  value: decision,
                  decoration: const InputDecoration(labelText: '处理结果'),
                  items: const [
                    DropdownMenuItem(value: 'in_review', child: Text('转入处理中')),
                    DropdownMenuItem(value: 'resolved', child: Text('已处理')),
                    DropdownMenuItem(value: 'dismissed', child: Text('驳回举报')),
                  ],
                  onChanged: (value) => setDialogState(() {
                    decision = value ?? 'in_review';
                    if (decision != 'resolved') hideIdea = false;
                  }),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: hideIdea,
                  onChanged: decision == 'resolved'
                      ? (value) => setDialogState(() => hideIdea = value ?? false)
                      : null,
                  title: const Text('同时将创意下架并转为私有草稿'),
                  subtitle: const Text('该操作会立即从公开探索中移除创意并关闭衍生许可'),
                ),
                TextField(
                  controller: noteController,
                  maxLines: 3,
                  maxLength: 2000,
                  decoration: const InputDecoration(labelText: '处理说明'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, {
                'status': decision,
                'hide_idea': hideIdea,
                'resolution_note': noteController.text.trim(),
              }),
              child: const Text('提交处理'),
            ),
          ],
        ),
      ),
    );
    noteController.dispose();
    if (payload == null) return;
    try {
      await ref.read(ideaServiceProvider).reviewReport(
            reportId: report['id'] as String,
            status: payload['status'] as String,
            hideIdea: payload['hide_idea'] as bool,
            resolutionNote: payload['resolution_note'] as String,
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('举报处理结果已保存')),
        );
        await _load();
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('处理失败：$error')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('社区举报管理')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: DropdownButtonFormField<String>(
              value: _status,
              decoration: const InputDecoration(labelText: '举报状态'),
              items: const [
                DropdownMenuItem(value: 'pending', child: Text('待处理')),
                DropdownMenuItem(value: 'in_review', child: Text('处理中')),
                DropdownMenuItem(value: 'resolved', child: Text('已处理')),
                DropdownMenuItem(value: 'dismissed', child: Text('已驳回')),
              ],
              onChanged: (value) {
                if (value == null) return;
                setState(() => _status = value);
                _load();
              },
            ),
          ),
          if (_loading) const LinearProgressIndicator(),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text('加载失败：$_error'),
            ),
          Expanded(
            child: _loading
                ? const SizedBox.shrink()
                : _items.isEmpty
                    ? const Center(child: Text('当前没有举报记录'))
                    : ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
                        itemCount: _items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          final report = _items[index];
                          final terminal = report['status'] == 'resolved' ||
                              report['status'] == 'dismissed';
                          return Card(
                            child: Padding(
                              padding: const EdgeInsets.all(14),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _reason(report['reason'] as String),
                                    style: Theme.of(context).textTheme.titleMedium,
                                  ),
                                  const SizedBox(height: 6),
                                  Text(report['idea_content'] as String? ?? ''),
                                  if ((report['description'] as String? ?? '').isNotEmpty) ...[
                                    const SizedBox(height: 6),
                                    Text('说明：${report['description']}'),
                                  ],
                                  const SizedBox(height: 8),
                                  Text('举报人：${report['reporter_username']}'),
                                  Text('状态：${report['status']} · 动作：${report['action_taken']}'),
                                  if ((report['resolution_note'] as String? ?? '').isNotEmpty)
                                    Text('处理说明：${report['resolution_note']}'),
                                  if (!terminal)
                                    Align(
                                      alignment: Alignment.centerRight,
                                      child: FilledButton.tonal(
                                        onPressed: () => _review(report),
                                        child: const Text('处理'),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
