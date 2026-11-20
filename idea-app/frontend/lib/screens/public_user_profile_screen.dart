import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/user_profile_provider.dart';
import '../theme/app_theme.dart';

/// 其他用户的公开主页：只展示公开资料和已公开署名的贡献。
class PublicUserProfileScreen extends ConsumerWidget {
  final String userId;

  const PublicUserProfileScreen({super.key, required this.userId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(userProfileProvider(userId));
    final contributions = ref.watch(userContributionsProvider(userId));

    return Scaffold(
      appBar: AppBar(title: const Text('创作者主页')),
      body: profile.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('暂时无法加载该用户主页'),
              TextButton(
                onPressed: () => ref.invalidate(userProfileProvider(userId)),
                child: const Text('重试'),
              ),
            ],
          ),
        ),
        data: (user) {
          final colors = AppColors.of(context);
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const SizedBox(height: 12),
              Center(
                child: CircleAvatar(
                  radius: 42,
                  backgroundColor: colors.gold,
                  child: Text(
                    user.username.isEmpty ? '?' : user.username[0].toUpperCase(),
                    style: const TextStyle(
                      fontSize: 34,
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
                    _stat('产生', user.stats.produced, colors.gold, colors),
                    _divider(colors.divider),
                    _stat('收集', user.stats.collected, colors.success, colors),
                    _divider(colors.divider),
                    _stat('被 Fork', user.stats.forkedByOthers, colors.forkAccent, colors),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              const Text(
                '公开贡献记录',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              contributions.when(
                loading: () => const Padding(
                  padding: EdgeInsets.all(20),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (error, stack) => Text(
                  '贡献记录暂时无法加载',
                  style: TextStyle(color: colors.textSecondary, fontSize: 13),
                ),
                data: (items) {
                  if (items.isEmpty) {
                    return Text(
                      '还没有公开展示的贡献记录',
                      style: TextStyle(color: colors.textSecondary, fontSize: 13),
                    );
                  }
                  return Column(
                    children: items.map((item) {
                      final ideaId = item['idea_id'] as String? ?? '';
                      final version = item['version_number']?.toString() ?? '-';
                      final ideaContent = item['idea_content'] as String? ?? '';
                      final contribution = item['contribution_content'] as String? ?? '';
                      final summary = item['change_summary'] as String? ?? '';
                      final publishedAt = item['published_at'] as String? ?? '';
                      return Card(
                        margin: const EdgeInsets.only(bottom: 10),
                        child: ListTile(
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 8,
                          ),
                          title: Text(
                            '版本 V$version · $ideaContent',
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
                                if (publishedAt.isNotEmpty) ...[
                                  const SizedBox(height: 4),
                                  Text(
                                    '版本发布时间：$publishedAt',
                                    style: TextStyle(
                                      color: colors.textSecondary,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: ideaId.isEmpty
                              ? null
                              : () => context.push('/idea/$ideaId'),
                        ),
                      );
                    }).toList(),
                  );
                },
              ),
            ],
          );
        },
      ),
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
          Text(
            label,
            style: TextStyle(fontSize: 12, color: colors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _divider(Color color) => Container(width: 1, height: 32, color: color);
}
