import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';

class CollaborationListScreen extends ConsumerStatefulWidget {
  const CollaborationListScreen({super.key});

  @override
  ConsumerState<CollaborationListScreen> createState() => _CollaborationListScreenState();
}

class _CollaborationListScreenState extends ConsumerState<CollaborationListScreen> {
  late Future<List<Map<String, dynamic>>> _workspaces;
  late Future<List<Map<String, dynamic>>> _invitations;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    final service = ref.read(collaborationServiceProvider);
    _workspaces = service.listMine();
    _invitations = service.getInbox();
  }

  Future<void> _create() async {
    final title = TextEditingController();
    final description = TextEditingController();
    final sources = TextEditingController();
    final form = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('创建异步协作'),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: title, decoration: const InputDecoration(labelText: '协作主题')),
            TextField(controller: description, decoration: const InputDecoration(labelText: '说明')),
            TextField(
              controller: sources,
              decoration: const InputDecoration(
                labelText: '来源创意 ID（至少一个，多个用逗号分隔）',
                helperText: '只填写你有权访问的创意 ID',
              ),
            ),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('创建')),
        ],
      ),
    );
    if (form != true) return;
    final ids = sources.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    try {
      final result = await ref.read(collaborationServiceProvider).create(
        title: title.text.trim(),
        description: description.text.trim().isEmpty ? null : description.text.trim(),
        sourceIdeaIds: ids,
      );
      if (!mounted) return;
      context.push('/collaborations/${result['id']}');
      setState(_reload);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('创建失败：$e')));
    }
  }

  Future<void> _respond(String id, bool accept) async {
    try {
      final service = ref.read(collaborationServiceProvider);
      if (accept) {
        await service.accept(id);
      } else {
        await service.decline(id);
      }
      if (mounted) setState(_reload);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('操作失败：$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('共创空间'),
        actions: [IconButton(onPressed: _create, icon: const Icon(Icons.add), tooltip: '创建协作')],
      ),
      body: RefreshIndicator(
        onRefresh: () async => setState(_reload),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('待处理邀请', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            FutureBuilder(
              future: _invitations,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const LinearProgressIndicator();
                }
                if (snapshot.hasError) return Text('邀请加载失败：${snapshot.error}');
                final items = snapshot.data ?? [];
                if (items.isEmpty) return const Text('暂无待处理邀请');
                return Column(children: items.map((item) => Card(
                  child: ListTile(
                    title: Text(item['title'] as String? ?? '协作邀请'),
                    subtitle: Text('角色：${item['role']}'),
                    trailing: Wrap(spacing: 4, children: [
                      IconButton(onPressed: () => _respond(item['collaboration_id'] as String, true), icon: const Icon(Icons.check_circle_outline)),
                      IconButton(onPressed: () => _respond(item['collaboration_id'] as String, false), icon: const Icon(Icons.close)),
                    ]),
                  ),
                )).toList());
              },
            ),
            const SizedBox(height: 24),
            Text('我的协作空间', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            FutureBuilder(
              future: _workspaces,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()));
                }
                if (snapshot.hasError) return Text('协作空间加载失败：${snapshot.error}');
                final items = snapshot.data ?? [];
                if (items.isEmpty) return const Text('还没有协作空间，创建一个开始异步共创吧。');
                return Column(children: items.map((item) => Card(
                  child: ListTile(
                    leading: const Icon(Icons.groups_outlined),
                    title: Text(item['title'] as String? ?? '未命名协作'),
                    subtitle: Text('身份：${item['member_role']} · 状态：${item['status']}'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push('/collaborations/${item['id']}'),
                  ),
                )).toList());
              },
            ),
          ],
        ),
      ),
    );
  }
}

class CollaborationDetailScreen extends ConsumerStatefulWidget {
  final String collaborationId;
  const CollaborationDetailScreen({super.key, required this.collaborationId});

  @override
  ConsumerState<CollaborationDetailScreen> createState() => _CollaborationDetailScreenState();
}

class _CollaborationDetailScreenState extends ConsumerState<CollaborationDetailScreen> {
  late Future<Map<String, dynamic>> _detail;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _detail = ref.read(collaborationServiceProvider).get(widget.collaborationId);
  }

  Future<String?> _ask(String title, String hint) async {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: TextField(controller: controller, autofocus: true, decoration: InputDecoration(hintText: hint)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('确定')),
        ],
      ),
    );
  }

  Future<void> _invite() async {
    final userId = await _ask('邀请协作者', '输入用户 ID');
    if (userId == null || userId.isEmpty) return;
    try {
      await ref.read(collaborationServiceProvider).invite(widget.collaborationId, userId, 'contributor');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('邀请已发送，接受前不会获得访问权')));
        setState(_reload);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('邀请失败：$e')));
    }
  }

  Future<void> _revoke(String userId) async {
    try {
      await ref.read(collaborationServiceProvider).revoke(widget.collaborationId, userId);
      if (mounted) setState(_reload);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('撤销成员失败：$e')));
    }
  }

  Future<void> _submit() async {
    final content = await _ask('提交异步贡献', '描述你的建议、修改或研究');
    if (content == null || content.isEmpty) return;
    try {
      await ref.read(collaborationServiceProvider).submit(widget.collaborationId, content);
      if (mounted) setState(_reload);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('提交失败：$e')));
    }
  }

  Future<void> _publish(List<dynamic> contributions) async {
    final contentController = TextEditingController();
    final customTextController = TextEditingController();
    var visibility = 'private';
    var licenseCode = 'attribution_adaptation';
    var allowFork = false;
    var confirmTerms = false;
    var confirmCustom = false;
    final selected = <String>{
      for (final raw in contributions)
        if ((raw as Map)['status'] == 'accepted') raw['id'] as String,
    };
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('发布协作成果'),
          content: SizedBox(
            width: 520,
            child: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextField(
                  controller: contentController,
                  maxLength: 300,
                  maxLines: 4,
                  decoration: const InputDecoration(labelText: '最终创意内容'),
                ),
                DropdownButtonFormField<String>(
                  value: visibility,
                  decoration: const InputDecoration(labelText: '发布范围'),
                  items: const [
                    DropdownMenuItem(value: 'private', child: Text('私有草稿')),
                    DropdownMenuItem(value: 'public', child: Text('公开发布')),
                  ],
                  onChanged: (value) => setDialogState(() {
                    visibility = value ?? 'private';
                    if (visibility != 'public') {
                      allowFork = false;
                      confirmTerms = false;
                    }
                  }),
                ),
                DropdownButtonFormField<String>(
                  value: licenseCode,
                  decoration: const InputDecoration(labelText: '授权方式'),
                  items: const [
                    DropdownMenuItem(value: 'all_rights_reserved', child: Text('保留所有权利')),
                    DropdownMenuItem(value: 'attribution', child: Text('署名')),
                    DropdownMenuItem(value: 'attribution_adaptation', child: Text('署名-允许改编')),
                    DropdownMenuItem(value: 'custom', child: Text('自定义授权')),
                  ],
                  onChanged: (value) => setDialogState(() => licenseCode = value ?? licenseCode),
                ),
                if (licenseCode == 'custom')
                  TextField(
                    controller: customTextController,
                    maxLines: 3,
                    decoration: const InputDecoration(labelText: '自定义授权条款'),
                  ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('允许后续衍生'),
                  value: allowFork,
                  onChanged: visibility == 'public'
                      ? (value) => setDialogState(() => allowFork = value)
                      : null,
                ),
                if (visibility == 'public')
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('我已阅读并确认本次公开授权条款'),
                    value: confirmTerms,
                    onChanged: (value) => setDialogState(() => confirmTerms = value ?? false),
                  ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('我已阅读并接受来源及祖先中的自定义授权条款（如有）'),
                  value: confirmCustom,
                  onChanged: (value) => setDialogState(() => confirmCustom = value ?? false),
                ),
                const Divider(),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text('纳入已采纳贡献（${selected.length}）'),
                ),
                ...contributions.map((raw) {
                  final item = Map<String, dynamic>.from(raw as Map);
                  if (item['status'] != 'accepted') return const SizedBox.shrink();
                  final id = item['id'] as String;
                  return CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(item['content'] as String? ?? ''),
                    value: selected.contains(id),
                    onChanged: (value) => setDialogState(() {
                      if (value == true) {
                        selected.add(id);
                      } else {
                        selected.remove(id);
                      }
                    }),
                  );
                }),
              ]),
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('取消')),
            FilledButton(
              onPressed: () {
                if (contentController.text.trim().isEmpty) return;
                Navigator.pop(dialogContext, {
                  'content': contentController.text.trim(),
                  'visibility': visibility,
                  'license_code': licenseCode,
                  'license_custom_text': customTextController.text.trim(),
                  'allow_fork': allowFork,
                  'confirm_terms': confirmTerms,
                  'confirm_custom_licenses': confirmCustom,
                  'accepted_contribution_ids': selected.toList(),
                });
              },
              child: const Text('确认发布'),
            ),
          ],
        ),
      ),
    );
    if (result == null) return;
    try {
      final published = await ref.read(collaborationServiceProvider).publish(
        id: widget.collaborationId,
        content: result['content'] as String,
        visibility: result['visibility'] as String,
        licenseCode: result['license_code'] as String,
        licenseCustomText: (result['license_custom_text'] as String).isEmpty
            ? null : result['license_custom_text'] as String,
        allowFork: result['allow_fork'] as bool,
        confirmTerms: result['confirm_terms'] as bool,
        confirmCustomLicenses: result['confirm_custom_licenses'] as bool,
        acceptedContributionIds: (result['accepted_contribution_ids'] as List).cast<String>(),
      );
      if (mounted) context.pushReplacement('/idea/${published['idea_id']}');
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('发布失败：$e')));
    }
  }

  Future<void> _review(String id, String decision) async {
    try {
      await ref.read(collaborationServiceProvider).review(widget.collaborationId, id, decision);
      if (mounted) setState(_reload);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('审核失败：$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('协作空间')),
      body: FutureBuilder(
        future: _detail,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return Center(child: Text('加载失败：${snapshot.error}'));
          final data = snapshot.data!;
          final isOwner = data['member_role'] == 'owner';
          final members = (data['members'] as List<dynamic>? ?? []);
          final sources = (data['sources'] as List<dynamic>? ?? []);
          final contributions = (data['contributions'] as List<dynamic>? ?? []);
          final publishedResult = data['published_result'] as Map<String, dynamic>?;
          return RefreshIndicator(
            onRefresh: () async => setState(_reload),
            child: ListView(padding: const EdgeInsets.all(16), children: [
              Text(data['title'] as String? ?? '', style: Theme.of(context).textTheme.headlineSmall),
              if ((data['description'] as String? ?? '').isNotEmpty) Text(data['description'] as String),
              if (publishedResult != null) ...[
                const SizedBox(height: 12),
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.task_alt),
                    title: const Text('协作成果已完成'),
                    subtitle: Text(
                      '${publishedResult['content']}\\n范围：${publishedResult['visibility']} · 授权：${publishedResult['license_code']}',
                    ),
                    isThreeLine: true,
                    trailing: publishedResult['idea_id'] != null
                        ? const Icon(Icons.open_in_new)
                        : null,
                    onTap: publishedResult['idea_id'] != null
                        ? () => context.push('/idea/${publishedResult['idea_id']}')
                        : null,
                  ),
                ),
              ],
              const SizedBox(height: 16),
              Row(children: [
                Text('成员（${members.length}）', style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                if (isOwner) IconButton(onPressed: _invite, icon: const Icon(Icons.person_add_alt_1)),
              ]),
              ...members.map((m) => ListTile(
                dense: true,
                leading: const Icon(Icons.person_outline),
                title: Text(m['username'] as String? ?? '成员'),
                subtitle: Text('${m['role']} · ${m['status']}'),
                trailing: isOwner && m['user_id'] != data['owner_id']
                    ? IconButton(
                        tooltip: '撤销成员',
                        icon: const Icon(Icons.person_remove_outlined),
                        onPressed: () => _revoke(m['user_id'] as String),
                      )
                    : null,
              )),
              const Divider(),
              Text('来源创意', style: Theme.of(context).textTheme.titleMedium),
              ...sources.map((s) => ListTile(
                dense: true,
                leading: Icon(s['accessible'] == true ? Icons.link : Icons.lock_outline),
                title: Text(s['accessible'] == true ? '可访问来源' : '受限来源（不授予原 Idea 权限）'),
              )),
              const Divider(),
              Row(children: [
                Text('异步贡献', style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                if (data['member_role'] == 'owner' || data['member_role'] == 'contributor')
                  IconButton(onPressed: _submit, icon: const Icon(Icons.add_comment_outlined)),
              ]),
              ...contributions.map((raw) {
                final item = Map<String, dynamic>.from(raw as Map);
                final pending = item['status'] == 'submitted';
                return Card(child: ListTile(
                  title: Text(item['content'] as String? ?? ''),
                  subtitle: Text('${item['contribution_type']} · ${item['status']}'),
                  trailing: isOwner && pending ? Wrap(spacing: 0, children: [
                    IconButton(onPressed: () => _review(item['id'] as String, 'accepted'), icon: const Icon(Icons.check)),
                    IconButton(onPressed: () => _review(item['id'] as String, 'rejected'), icon: const Icon(Icons.close)),
                  ]) : null,
                ));
              }),
              if (isOwner && data['status'] == 'draft')
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  child: FilledButton.icon(
                    onPressed: () => _publish(contributions),
                    icon: const Icon(Icons.publish),
                    label: const Text('发布协作成果'),
                  ),
                ),
              const Divider(),
              Text('协作动态', style: Theme.of(context).textTheme.titleMedium),
              ...(data['events'] as List<dynamic>? ?? []).map((raw) {
                final event = Map<String, dynamic>.from(raw as Map);
                return ListTile(dense: true, leading: const Icon(Icons.history), title: Text(event['event_type'] as String? ?? '事件'));
              }),
            ]),
          );
        },
      ),
    );
  }
}
