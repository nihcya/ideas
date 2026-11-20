import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/user.dart';
import '../providers/auth_provider.dart';
import '../providers/vault_provider.dart';
import '../providers/user_profile_provider.dart';
import '../theme/app_theme.dart';

/// 个人主页：思维森林
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);
    final user = authState.maybeWhen(
      authenticated: (u) => u,
      orElse: () => null,
    );

    if (user == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('我')),
        body: const Center(child: Text('请先登录')),
      );
    }

    final asyncVault = ref.watch(vaultProvider);
    final asyncContributions = ref.watch(userContributionsProvider(user.id));
    return Scaffold(
      appBar: AppBar(
        title: const Text('我'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => context.push('/notifications'),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => context.push('/settings'),
          ),
        ],
      ),
      body: asyncVault.when(
        data: (vault) => _ProfileBody(
          user: user,
          produced: vault.stats.produced,
          collected: vault.stats.collected,
          forkedByOthers: vault.stats.forkedByOthers,
          contributions: asyncContributions,
          onLogout: () => _logout(context, ref),
        ),
        loading: () => _ProfileBody(
          user: user,
          produced: 0,
          collected: 0,
          forkedByOthers: 0,
          contributions: asyncContributions,
          onLogout: () => _logout(context, ref),
        ),
        error: (e, st) => _ProfileBody(
          user: user,
          produced: 0,
          collected: 0,
          forkedByOthers: 0,
          onLogout: () => _logout(context, ref),
        ),
      ),
    );
  }

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(logoutActionProvider)();
    } catch (_) {
      // 即使登出失败也跳转登录
    }
    if (context.mounted) context.go('/auth');
  }
}

class _ProfileBody extends StatelessWidget {
  final UserBrief user;
  final int produced;
  final int collected;
  final int forkedByOthers;
  final AsyncValue<List<Map<String, dynamic>>> contributions;
  final VoidCallback onLogout;

  const _ProfileBody({
    required this.user,
    required this.produced,
    required this.collected,
    required this.forkedByOthers,
    required this.contributions,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context) {
    final colors = AppColors.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const SizedBox(height: 16),
        Center(
          child: CircleAvatar(
            radius: 44,
            backgroundColor: colors.gold,
            child: Text(
              user.username.isNotEmpty ? user.username[0].toUpperCase() : '?',
              style: const TextStyle(
                fontSize: 36,
                color: Colors.black,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          user.username,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 6),
        Text(
          user.bio.isEmpty ? '还没有介绍' : user.bio,
          textAlign: TextAlign.center,
          style: TextStyle(color: colors.textSecondary, fontSize: 13),
        ),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.symmetric(vertical: 16),
          decoration: BoxDecoration(
            color: colors.surface,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              _stat('产生', produced, colors.gold, colors),
              _divider(colors.divider),
              _stat('收集', collected, colors.success, colors),
              _divider(colors.divider),
              _stat('被 Fork', forkedByOthers, colors.forkAccent, colors),
            ],
          ),
        ),

        const SizedBox(height: 28),
        const Text(
          '贡献记录',
          style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 10),
        contributions.when(
          data: (items) {
            if (items.isEmpty) {
              return Text(
                '还没有公开展示的贡献记录',
                style: TextStyle(color: colors.textSecondary, fontSize: 13),
              );
            }
            return Column(
              children: items.map((item) {
                final versionNumber = item['version_number'] ?? '-';
                final summary = item['change_summary'] as String? ?? '';
                final contribution =
                    item['contribution_content'] as String? ?? '';
                final ideaContent = item['idea_content'] as String? ?? '';
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 6,
                    ),
                    title: Text(
                      '版本 V$versionNumber · $ideaContent',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (summary.isNotEmpty) Text(summary),
                          const SizedBox(height: 4),
                          Text(
                            '贡献：$contribution',
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push('/idea/${item['idea_id']}'),
                  ),
                );
              }).toList(),
            );
          },
          loading: () => const Center(
            child: Padding(
              padding: EdgeInsets.all(12),
              child: CircularProgressIndicator(),
            ),
          ),
          error: (error, stack) => Text(
            '贡献记录暂时无法加载',
            style: TextStyle(color: colors.textSecondary, fontSize: 13),
          ),
        ),

        const SizedBox(height: 24),
        ListTile(
          leading: const Icon(Icons.notifications_outlined),
          title: const Text('通知'),
          trailing: Icon(Icons.chevron_right, color: colors.textSecondary),
          onTap: () => context.push('/notifications'),
        ),
        ListTile(
          leading: const Icon(Icons.settings_outlined),
          title: const Text('设置'),
          trailing: Icon(Icons.chevron_right, color: colors.textSecondary),
          onTap: () => context.push('/settings'),
        ),
        const SizedBox(height: 24),
        TextButton(
          onPressed: onLogout,
          style: TextButton.styleFrom(foregroundColor: colors.error),
          child: const Text('退出登录'),
        ),
      ],
    );
  }

  Widget _stat(String label, int value, Color color, AppColors colors) {
    return Expanded(
      child: Column(
        children: [
          Text(
            '$value',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(label,
              style:
                  TextStyle(fontSize: 12, color: colors.textSecondary)),
        ],
      ),
    );
  }

  Widget _divider(Color color) {
    return Container(
      width: 1,
      height: 32,
      color: color,
    );
  }
}
