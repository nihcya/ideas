import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';

class IdeaInvitesScreen extends ConsumerStatefulWidget {
  const IdeaInvitesScreen({super.key});

  @override
  ConsumerState<IdeaInvitesScreen> createState() => _IdeaInvitesScreenState();
}

class _IdeaInvitesScreenState extends ConsumerState<IdeaInvitesScreen> {
  late Future<List<Map<String, dynamic>>> _pending;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    _pending = ref.read(ideaServiceProvider).getPendingIdeaInvites();
  }

  Future<void> _respond(
    Map<String, dynamic> invite, {
    required bool accept,
  }) async {
    final ideaId = invite['idea_id'] as String;
    final inviteId = invite['invite_id'] as String;
    try {
      if (accept) {
        await ref.read(ideaServiceProvider).acceptPrivateIdeaInvite(
              ideaId: ideaId,
              inviteId: inviteId,
            );
      } else {
        await ref.read(ideaServiceProvider).declinePrivateIdeaInvite(
              ideaId: ideaId,
              inviteId: inviteId,
            );
      }
      if (!mounted) return;
      setState(_load);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(accept ? '已接受邀请' : '已拒绝邀请')),
      );
      if (accept) context.push('/idea/$ideaId');
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.toString())));
      setState(_load);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('创意邀请')),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _pending,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('加载失败：${snapshot.error}'));
          }
          final items = snapshot.data ?? const [];
          if (items.isEmpty) {
            return const Center(child: Text('暂时没有待处理的创意邀请'));
          }
          return RefreshIndicator(
            onRefresh: () async => setState(_load),
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: items.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final invite = items[index];
                final inviter = invite['inviter'] as Map<String, dynamic>;
                final role = invite['role'] == 'contributor' ? '协作者' : '查看者';
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${inviter['username']} 邀请你访问一个私有创意',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        Text(invite['idea_content'] as String? ?? ''),
                        const SizedBox(height: 8),
                        Text('权限：$role', style: Theme.of(context).textTheme.bodySmall),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton(
                                onPressed: () => _respond(invite, accept: false),
                                child: const Text('拒绝'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: FilledButton(
                                onPressed: () => _respond(invite, accept: true),
                                child: const Text('接受邀请'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
