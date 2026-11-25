import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';
import '../providers/user_profile_provider.dart';
import '../models/user.dart';
import '../theme/app_theme.dart';

/// 其他用户的公开主页：只展示公开资料和已公开署名的贡献。
class PublicUserProfileScreen extends ConsumerStatefulWidget {
  final String userId;

  const PublicUserProfileScreen({super.key, required this.userId});

  @override
  ConsumerState<PublicUserProfileScreen> createState() =>
      _PublicUserProfileScreenState();
}

class _PublicUserProfileScreenState
    extends ConsumerState<PublicUserProfileScreen> {
  static const int _pageSize = 20;
  final List<Map<String, dynamic>> _contributions = [];
  int _offset = 0;
  bool _loadingContributions = true;
  bool _loadingMore = false;
  bool _hasMore = false;
  String? _contributionError;
  int _requestGeneration = 0;

  @override
  void initState() {
    super.initState();
    _loadContributions(reset: true);
  }

  @override
  void didUpdateWidget(covariant PublicUserProfileScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.userId != widget.userId) {
      _loadContributions(reset: true);
    }
  }

  Future<void> _loadContributions({bool reset = false}) async {
    if ((_loadingMore || _loadingContributions) && !reset) return;
    if (reset) {
      _requestGeneration += 1;
      setState(() {
        _loadingContributions = true;
        _loadingMore = false;
        _contributionError = null;
        _offset = 0;
        _hasMore = false;
        _contributions.clear();
      });
    } else {
      setState(() {
        _loadingMore = true;
        _contributionError = null;
      });
    }

    final generation = _requestGeneration;
    try {
      final page = await ref.read(userServiceProvider).getUserContributionsPage(
            widget.userId,
            limit: _pageSize,
            offset: reset ? 0 : _offset,
          );
      if (!mounted || generation != _requestGeneration) return;
      final items = List<Map<String, dynamic>>.from(page['items'] as List);
      setState(() {
        _contributions.addAll(items);
        _offset = (page['offset'] as int? ?? _offset) + items.length;
        _hasMore = page['has_more'] as bool? ?? false;
        _loadingContributions = false;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted || generation != _requestGeneration) return;
      setState(() {
        _contributionError = '贡献记录暂时无法加载';
        _loadingContributions = false;
        _loadingMore = false;
      });
    }
  }

  Future<void> _refresh() async {
    ref.invalidate(userProfileProvider(widget.userId));
    await _loadContributions(reset: true);
  }

  Future<void> _toggleFollow(UserProfile user) async {
    try {
      final service = ref.read(userServiceProvider);
      if (user.isFollowing) {
        await service.unfollowUser(widget.userId);
      } else {
        await service.followUser(widget.userId);
      }
      if (mounted) {
        ref.invalidate(userProfileProvider(widget.userId));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(user.isFollowing ? '已取消关注' : '已关注该创作者')),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('关注操作失败：$error')),
        );
      }
    }
  }


  @override
  Widget build(BuildContext context) {
    final profile = ref.watch(userProfileProvider(widget.userId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('创作者主页'),
        actions: [
          IconButton(
            tooltip: '刷新',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: profile.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('暂时无法加载该用户主页'),
              TextButton(
                onPressed: () => ref.invalidate(userProfileProvider(widget.userId)),
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
              if (user.canFollow) ...[
                const SizedBox(height: 14),
                Center(
                  child: user.isFollowing
                      ? OutlinedButton.icon(
                          onPressed: () => _toggleFollow(user),
                          icon: const Icon(Icons.check),
                          label: const Text('已关注'),
                        )
                      : FilledButton.icon(
                          onPressed: () => _toggleFollow(user),
                          icon: const Icon(Icons.person_add_alt_1),
                          label: const Text('关注创作者'),
                        ),
                ),
              ],
              const SizedBox(height: 14),
              Center(
                child: Text(
                  '粉丝 ${user.stats.followers}  ·  关注 ${user.stats.following}',
                  style: TextStyle(color: colors.textSecondary, fontSize: 12),
                ),
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
              _buildContributions(context, colors),
            ],
          );
        },
      ),
    );
  }

  Widget _buildContributions(BuildContext context, AppColors colors) {
    if (_loadingContributions && _contributions.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(20),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (_contributionError != null && _contributions.isEmpty) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(_contributionError!,
              style: TextStyle(color: colors.textSecondary, fontSize: 13)),
          TextButton(
            onPressed: () => _loadContributions(reset: true),
            child: const Text('重试'),
          ),
        ],
      );
    }
    if (_contributions.isEmpty) {
      return Text(
        '还没有公开展示的贡献记录',
        style: TextStyle(color: colors.textSecondary, fontSize: 13),
      );
    }

    return Column(
      children: [
        ..._contributions.map((item) {
          final ideaId = item['idea_id'] as String? ?? '';
          final versionId = item['version_id'] as String? ?? '';
          final version = item['version_number']?.toString() ?? '-';
          final ideaContent = item['idea_content'] as String? ?? '';
          final contribution = item['contribution_content'] as String? ?? '';
          final summary = item['change_summary'] as String? ?? '';
          final publishedAt = item['published_at'] as String? ?? '';
          final timelineUri = Uri(
            path: '/idea/$ideaId/timeline',
            queryParameters: versionId.isEmpty ? null : {'version': versionId},
          );
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
                  : () => context.push(timelineUri.toString()),
            ),
          );
        }),
        if (_contributionError != null)
          Text(
            _contributionError!,
            style: TextStyle(color: colors.textSecondary, fontSize: 12),
          ),
        if (_hasMore)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: OutlinedButton(
              onPressed: _loadingMore ? null : () => _loadContributions(),
              child: _loadingMore
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('加载更多贡献'),
            ),
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
          Text(label, style: TextStyle(fontSize: 12, color: colors.textSecondary)),
        ],
      ),
    );
  }

  Widget _divider(Color color) => Container(width: 1, height: 32, color: color);
}
