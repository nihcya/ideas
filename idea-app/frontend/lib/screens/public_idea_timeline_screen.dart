import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';

/// 公开创意的只读版本时间线。
class PublicIdeaTimelineScreen extends ConsumerStatefulWidget {
  final String ideaId;

  const PublicIdeaTimelineScreen({super.key, required this.ideaId});

  @override
  ConsumerState<PublicIdeaTimelineScreen> createState() =>
      _PublicIdeaTimelineScreenState();
}

class _PublicIdeaTimelineScreenState
    extends ConsumerState<PublicIdeaTimelineScreen> {
  List<Map<String, dynamic>> _versions = [];
  bool _loading = true;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _failed = false;
    });
    try {
      final versions = await ref
          .read(ideaServiceProvider)
          .getPublicIdeaVersions(widget.ideaId);
      if (!mounted) return;
      setState(() {
        _versions = versions;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _failed = true;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('版本时间线'),
        actions: [
          IconButton(
            tooltip: '刷新',
            onPressed: _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _failed
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('版本时间线暂时无法加载'),
                      TextButton(onPressed: _load, child: const Text('重试')),
                    ],
                  ),
                )
              : _versions.isEmpty
                  ? const Center(child: Text('该创意暂时没有已发布的版本记录'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _versions.length,
                      itemBuilder: (context, index) {
                        final version = _versions[index];
                        final number =
                            version['version_number']?.toString() ?? '-';
                        final content = version['content'] as String? ?? '';
                        final summary =
                            version['change_summary'] as String? ?? '';
                        final publishedAt =
                            version['published_at']?.toString() ?? '';
                        final attributions =
                            (version['attributions'] as List<dynamic>?) ?? [];
                        return Card(
                          margin: const EdgeInsets.only(bottom: 12),
                          child: ExpansionTile(
                            initiallyExpanded: index == 0,
                            leading: const Icon(Icons.history),
                            title: Text('版本 V$number'),
                            subtitle: Text(
                              publishedAt.isEmpty
                                  ? '已发布'
                                  : '发布时间：$publishedAt',
                            ),
                            childrenPadding:
                                const EdgeInsets.fromLTRB(16, 0, 16, 16),
                            children: [
                              Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  content,
                                  style: Theme.of(context).textTheme.bodyLarge,
                                ),
                              ),
                              if (summary.isNotEmpty) ...[
                                const SizedBox(height: 10),
                                Align(
                                  alignment: Alignment.centerLeft,
                                  child: Text('版本说明：$summary'),
                                ),
                              ],
                              const Divider(height: 24),
                              Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  '贡献署名（${attributions.length}）',
                                  style: Theme.of(context).textTheme.titleSmall,
                                ),
                              ),
                              if (attributions.isEmpty)
                                const Align(
                                  alignment: Alignment.centerLeft,
                                  child: Padding(
                                    padding: EdgeInsets.symmetric(vertical: 8),
                                    child: Text('此版本没有关联协作者贡献'),
                                  ),
                                ),
                              ...attributions.map((raw) {
                                final item = Map<String, dynamic>.from(
                                  raw as Map,
                                );
                                final authorId =
                                    item['author_id']?.toString() ?? '';
                                return ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  leading:
                                      const Icon(Icons.person_outline),
                                  title: Text(
                                    item['author_name']?.toString() ?? '协作者',
                                  ),
                                  subtitle: Text(
                                    item['content']?.toString() ?? '',
                                  ),
                                  trailing: authorId.isEmpty
                                      ? null
                                      : const Icon(Icons.chevron_right),
                                  onTap: authorId.isEmpty
                                      ? null
                                      : () => context.push('/user/$authorId'),
                                  dense: true,
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
