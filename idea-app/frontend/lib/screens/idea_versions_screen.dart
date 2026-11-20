import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/api_provider.dart';

class IdeaVersionsScreen extends ConsumerStatefulWidget {
  final String ideaId;
  final String? highlightVersionId;
  const IdeaVersionsScreen({super.key, required this.ideaId, this.highlightVersionId});

  @override
  ConsumerState<IdeaVersionsScreen> createState() => _IdeaVersionsScreenState();
}

class _IdeaVersionsScreenState extends ConsumerState<IdeaVersionsScreen> {
  final _content = TextEditingController();
  final _summary = TextEditingController();
  List<Map<String, dynamic>> _versions = [];
  List<Map<String, dynamic>> _contributions = [];
  final Set<String> _selected = {};
  String? _draftId;
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() { super.initState(); _load(); }
  @override
  void dispose() { _content.dispose(); _summary.dispose(); super.dispose(); }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final service = ref.read(ideaServiceProvider);
      final versions = await service.getIdeaVersions(widget.ideaId);
      final contributions = await service.getIdeaContributions(widget.ideaId);
      final drafts = versions.where((v) => v['status'] == 'draft');
      final draft = drafts.isEmpty ? null : drafts.first;
      if (!mounted) return;
      setState(() {
        _versions = versions;
        _contributions = contributions.where((v) => v['status'] == 'accepted').toList();
        _draftId = draft?['id'] as String?;
        if (draft != null) {
          _content.text = draft['content'] as String? ?? '';
          _summary.text = draft['change_summary'] as String? ?? '';
          _selected..clear()..addAll(((draft['attributions'] as List<dynamic>?) ?? [])
              .map((e) => (e as Map)['contribution_id'] as String));
        }
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('加载版本失败：$e')));
    }
  }

  Future<void> _save() async {
    if (_content.text.trim().isEmpty) return;
    setState(() => _saving = true);
    try {
      final service = ref.read(ideaServiceProvider);
      if (_draftId == null) {
        final result = await service.createIdeaVersionDraft(
          ideaId: widget.ideaId, content: _content.text.trim(),
          changeSummary: _summary.text.trim().isEmpty ? null : _summary.text.trim(),
          contributionIds: _selected.toList(),
        );
        _draftId = result['id'] as String;
      } else {
        await service.updateIdeaVersionDraft(
          ideaId: widget.ideaId, versionId: _draftId!, content: _content.text.trim(),
          changeSummary: _summary.text.trim().isEmpty ? null : _summary.text.trim(),
          contributionIds: _selected.toList(),
        );
      }
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('版本草稿已保存')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('保存失败：$e')));
    } finally { if (mounted) setState(() => _saving = false); }
  }

  Future<void> _publish() async {
    final id = _draftId;
    if (id == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('发布此版本？'),
        content: const Text('发布后将更新创意当前内容，并锁定本次贡献署名。该操作不可撤销。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('返回检查')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('确认发布')),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _saving = true);
    try {
      await ref.read(ideaServiceProvider).publishIdeaVersion(ideaId: widget.ideaId, versionId: id);
      _draftId = null; _content.clear(); _summary.clear(); _selected.clear();
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('版本已发布，创意内容已更新')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('发布失败：$e')));
    } finally { if (mounted) setState(() => _saving = false); }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return Scaffold(
      appBar: AppBar(title: const Text('版本管理'), actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text('版本草稿', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        TextField(controller: _content, minLines: 3, maxLines: 7, maxLength: 300,
          decoration: const InputDecoration(labelText: '整合后的创意内容', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _summary, minLines: 2, maxLines: 4, maxLength: 2000,
          decoration: const InputDecoration(labelText: '本次版本变更说明（选填）', border: OutlineInputBorder())),
        const SizedBox(height: 12),
        Text('贡献归属（仅显示已采纳贡献）', style: Theme.of(context).textTheme.titleMedium),
        if (_contributions.isEmpty) const Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Text('暂无已采纳贡献，可先保存不关联贡献的版本')),
        ..._contributions.map((item) {
          final id = item['id'] as String;
          final publishedVersion = item['published_version'] as Map<String, dynamic>?;
          final isConsumed = publishedVersion != null;
          return CheckboxListTile(
            value: !isConsumed && _selected.contains(id),
            onChanged: isConsumed ? null : (value) => setState(() { if (value == true) { _selected.add(id); } else { _selected.remove(id); } }),
            title: Text(item['author_username'] as String? ?? '协作者'),
            subtitle: Text(
              (item['content'] as String? ?? '') +
              (isConsumed ? '（已归属其他版本）' : ''),
            ),
            controlAffinity: ListTileControlAffinity.leading, contentPadding: EdgeInsets.zero,
          );
        }),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: OutlinedButton(onPressed: _saving ? null : _save, child: Text(_draftId == null ? '保存版本草稿' : '更新草稿'))),
          const SizedBox(width: 10),
          Expanded(child: FilledButton(onPressed: _saving || _draftId == null ? null : _publish, child: const Text('审核并发布'))),
        ]),
        const Divider(height: 36),
        Text('版本历史', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        ..._versions.where((v) => v['status'] == 'published').map((version) {
          final attrs = (version['attributions'] as List<dynamic>?) ?? [];
          final publishedAt = version['published_at']?.toString();
          final isHighlighted = version['id'] == widget.highlightVersionId;
          return Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: ExpansionTile(
              initiallyExpanded: isHighlighted,
              leading: const Icon(Icons.history),
              title: Text('版本 ' + version['version_number'].toString()),
              subtitle: Text(publishedAt == null ? '已发布' : '发布时间：' + publishedAt),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              children: [
                Align(alignment: Alignment.centerLeft, child: Text(version['content'] as String? ?? '', style: Theme.of(context).textTheme.bodyLarge)),
                if ((version['change_summary'] as String?)?.isNotEmpty == true) ...[
                  const SizedBox(height: 10),
                  Align(alignment: Alignment.centerLeft, child: Text('版本说明：' + (version['change_summary'] as String))),
                ],
                const Divider(height: 24),
                Align(alignment: Alignment.centerLeft, child: Text('贡献归属（' + attrs.length.toString() + '）', style: Theme.of(context).textTheme.titleSmall)),
                if (attrs.isEmpty)
                  const Align(alignment: Alignment.centerLeft, child: Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Text('此版本没有关联协作者贡献'))),
                ...attrs.map((raw) {
                  final attr = raw as Map;
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.person_outline),
                    title: Text(attr['author_name']?.toString() ?? '协作者'),
                    subtitle: Text(attr['content']?.toString() ?? ''),
                    dense: true,
                  );
                }),
              ],
            ),
          );
        }),
      ]),
    );
  }
}
