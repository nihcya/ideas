import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';

class IdeaContributionsScreen extends ConsumerStatefulWidget {
  final String ideaId;
  final bool isOwner;

  const IdeaContributionsScreen({
    super.key,
    required this.ideaId,
    required this.isOwner,
  });

  @override
  ConsumerState<IdeaContributionsScreen> createState() =>
      _IdeaContributionsScreenState();
}

class _IdeaContributionsScreenState
    extends ConsumerState<IdeaContributionsScreen> {
  final _contentController = TextEditingController();
  final _noteController = TextEditingController();
  late Future<List<Map<String, dynamic>>> _items;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _contentController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  void _load() {
    _items = ref.read(ideaServiceProvider).getIdeaContributions(widget.ideaId);
  }

  Future<void> _refresh() async {
    setState(_load);
    await _items;
  }

  Future<void> _submit() async {
    final content = _contentController.text.trim();
    if (content.isEmpty) return;
    setState(() => _submitting = true);
    try {
      await ref.read(ideaServiceProvider).submitIdeaContribution(
            ideaId: widget.ideaId,
            content: content,
            note: _noteController.text.trim().isEmpty
                ? null
                : _noteController.text.trim(),
          );
      _contentController.clear();
      _noteController.clear();
      if (!mounted) return;
      setState(_load);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('贡献已提交，等待作者审核')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _review(String id, String decision) async {
    try {
      await ref.read(ideaServiceProvider).reviewIdeaContribution(
            ideaId: widget.ideaId,
            contributionId: id,
            decision: decision,
          );
      if (!mounted) return;
      setState(_load);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(decision == 'accepted' ? '已采纳贡献' : '已拒绝贡献')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  String _status(String value) {
    switch (value) {
      case 'submitted':
        return '待审核';
      case 'accepted':
        return '已采纳';
      case 'rejected':
        return '已拒绝';
      case 'withdrawn':
        return '已撤回';
      default:
        return value;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('异步贡献'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh),
            onPressed: () => setState(_load),
          ),
        ],
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _items,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('加载失败：${snapshot.error}'));
          }
          final items = snapshot.data ?? const [];
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (!widget.isOwner) ...[
                  Text('提交你的创意建议', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _contentController,
                    minLines: 3,
                    maxLines: 7,
                    maxLength: 3000,
                    decoration: const InputDecoration(
                      hintText: '描述你的改进方案、补充思路或不同方向',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _noteController,
                    maxLength: 1000,
                    decoration: const InputDecoration(
                      hintText: '补充说明（选填）',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  FilledButton(
                    onPressed: _submitting ? null : _submit,
                    child: _submitting
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('提交贡献'),
                  ),
                  const Divider(height: 32),
                ],
                Text(
                  widget.isOwner ? '收到的贡献' : '我的贡献记录',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                if (items.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Center(child: Text('还没有贡献记录')),
                  ),
                ...items.map((item) {
                  final status = item['status'] as String? ?? '';
                  final id = item['id'] as String;
                  final publishedVersion = item['published_version'] as Map<String, dynamic>?;
                  return Card(
                    margin: const EdgeInsets.only(bottom: 10),
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  item['author_username'] as String? ?? '协作者',
                                  style: const TextStyle(fontWeight: FontWeight.w600),
                                ),
                              ),
                              Chip(label: Text(_status(status))),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(item['content'] as String? ?? ''),
                          if ((item['note'] as String?)?.isNotEmpty == true) ...[
                            const SizedBox(height: 6),
                            Text(
                              '说明：${item['note']}',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                          if (widget.isOwner && status == 'submitted') ...[
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                Expanded(
                                  child: OutlinedButton(
                                    onPressed: () => _review(id, 'rejected'),
                                    child: const Text('拒绝'),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: FilledButton(
                                    onPressed: () => _review(id, 'accepted'),
                                    child: const Text('采纳'),
                                  ),
                                ),
                              ],
                            ),
                          ],
                          if (publishedVersion != null) ...[
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                const Icon(Icons.link, size: 16),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    '已纳入版本 V${publishedVersion['version_number']}',
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ),
                                TextButton(
                                  onPressed: () => context.push(
                                    '/idea/${widget.ideaId}/versions?version=${publishedVersion['id']}',
                                  ),
                                  child: const Text('查看版本与署名'),
                                ),
                              ],
                            ),
                            if ((item['attribution_content_snapshot'] as String?)?.isNotEmpty == true)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text(
                                  '版本署名内容：${item['attribution_content_snapshot']}',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ),
                          ],
                          if ((item['review_note'] as String?)?.isNotEmpty == true)
                            Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(
                                '作者反馈：${item['review_note']}',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ),
                        ],
                      ),
                    ),
                  );
                }),
              ],
            ),
          );
        },
      ),
    );
  }
}
