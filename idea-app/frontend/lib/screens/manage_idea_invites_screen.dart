import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/api_provider.dart';

class ManageIdeaInvitesScreen extends ConsumerStatefulWidget {
  final String ideaId;

  const ManageIdeaInvitesScreen({super.key, required this.ideaId});

  @override
  ConsumerState<ManageIdeaInvitesScreen> createState() =>
      _ManageIdeaInvitesScreenState();
}

class _ManageIdeaInvitesScreenState
    extends ConsumerState<ManageIdeaInvitesScreen> {
  final _userIdController = TextEditingController();
  String _role = 'viewer';
  late Future<List<Map<String, dynamic>>> _invites;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _userIdController.dispose();
    super.dispose();
  }

  void _load() {
    _invites = ref.read(ideaServiceProvider).getIdeaInvites(widget.ideaId);
  }

  Future<void> _invite() async {
    final userId = _userIdController.text.trim();
    if (userId.isEmpty) return;
    setState(() => _submitting = true);
    try {
      await ref.read(ideaServiceProvider).inviteToPrivateIdea(
            ideaId: widget.ideaId,
            userId: userId,
            role: _role,
          );
      _userIdController.clear();
      setState(_load);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('邀请已发送')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _revoke(String inviteId) async {
    try {
      await ref.read(ideaServiceProvider).revokePrivateIdeaInvite(
            ideaId: widget.ideaId,
            inviteId: inviteId,
          );
      setState(_load);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'pending':
        return '待接受';
      case 'accepted':
        return '已接受';
      case 'declined':
        return '已拒绝';
      case 'revoked':
        return '已撤销';
      default:
        return status;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('管理协作者')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            '通过用户 ID 邀请他人访问这个私有创意。对方接受前不会获得访问权；撤销后访问权立即失效。',
            style: TextStyle(height: 1.5),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _userIdController,
            decoration: const InputDecoration(
              labelText: '受邀用户 ID',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            value: _role,
            decoration: const InputDecoration(
              labelText: '邀请权限',
              border: OutlineInputBorder(),
            ),
            items: const [
              DropdownMenuItem(value: 'viewer', child: Text('查看者')),
              DropdownMenuItem(value: 'contributor', child: Text('协作者')),
            ],
            onChanged: _submitting
                ? null
                : (value) => setState(() => _role = value ?? 'viewer'),
          ),
          const SizedBox(height: 10),
          FilledButton(
            onPressed: _submitting ? null : _invite,
            child: _submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('发送邀请'),
          ),
          const Divider(height: 32),
          Text('邀请记录', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _invites,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Text('加载失败：${snapshot.error}');
              }
              final items = snapshot.data ?? const [];
              if (items.isEmpty) return const Text('还没有邀请记录');
              return Column(
                children: items.map((invite) {
                  final status = invite['status'] as String? ?? '';
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(invite['username'] as String? ?? '未知用户'),
                    subtitle: Text(
                      '${invite['role'] == 'contributor' ? '协作者' : '查看者'} · ${_statusLabel(status)}',
                    ),
                    trailing: status == 'revoked'
                        ? null
                        : IconButton(
                            tooltip: '撤销邀请 / 访问权',
                            icon: const Icon(Icons.person_remove_outlined),
                            onPressed: () => _revoke(invite['invite_id'] as String),
                          ),
                  );
                }).toList(),
              );
            },
          ),
        ],
      ),
    );
  }
}
