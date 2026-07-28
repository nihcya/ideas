import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/explore_provider.dart';
import '../widgets/circle_canvas.dart';

/// 主页探索页：圆圈画布 + 强制随机激发
class ExploreScreen extends ConsumerStatefulWidget {
  const ExploreScreen({super.key});

  @override
  ConsumerState<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends ConsumerState<ExploreScreen> {
  bool _loadingMore = false;

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _loadMore() async {
    if (_loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      await ref.read(exploreProvider.notifier).loadMore();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _refresh() async {
    await ref.read(exploreProvider.notifier).refresh();
  }

  void _onCircleTap(String id) {
    context.push('/idea/$id');
  }

  @override
  Widget build(BuildContext context) {
    final asyncCircles = ref.watch(exploreProvider);
    final hasMore = ref.watch(exploreProvider.notifier).hasMore;
    return Scaffold(
      appBar: AppBar(
        title: const Text('点子'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => context.push('/notifications'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: asyncCircles.when(
          data: (circles) {
            if (circles.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 240),
                  Center(
                    child: Text(
                      '等待灵感涌现...',
                      style: TextStyle(color: Color(0xFF9A9AA0)),
                    ),
                  ),
                ],
              );
            }
            return Stack(
              children: [
                CircleCanvas(
                  circles: circles,
                  onTap: _onCircleTap,
                  hasMore: hasMore,
                  onLoadMore: _loadMore,
                ),
                if (_loadingMore)
                  const Positioned(
                    bottom: 24,
                    left: 0,
                    right: 0,
                    child: Center(
                      child: SizedBox(
                        height: 24,
                        width: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  ),
              ],
            );
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, st) => ListView(
            children: [
              const SizedBox(height: 200),
              Center(child: Text('加载失败：$e')),
              const SizedBox(height: 16),
              Center(
                child: TextButton(
                  onPressed: _refresh,
                  child: const Text('重试'),
                ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/create'),
        backgroundColor: const Color(0xFFFFD700),
        foregroundColor: Colors.black,
        child: const Icon(Icons.add),
      ),
    );
  }
}
