import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/idea.dart';
import 'api_provider.dart';

/// 探索页 Notifier — 管理圆圈列表，支持刷新和加载更多
class ExploreNotifier extends AsyncNotifier<List<CircleData>> {
  int _offset = 0;
  bool _hasMore = true;
  ExploreFilters _filters = const ExploreFilters();

  ExploreFilters get filters => _filters;

  Future<void> setFilters(ExploreFilters filters) async {
    _filters = filters;
    await refresh();
  }

  @override
  Future<List<CircleData>> build() async {
    _offset = 0;
    _hasMore = true;
    return _fetch(offset: 0);
  }

  Future<List<CircleData>> _fetch({required int offset}) async {
    final ideaService = ref.read(ideaServiceProvider);
    final res = await ideaService.getExplore(
      offset: offset,
      query: _filters.query,
      sort: _filters.sort,
      licenseCode: _filters.licenseCode,
      allowFork: _filters.allowFork,
      source: _filters.source,
    );
    _offset = offset + res.circles.length;
    _hasMore = res.hasMore;
    return res.circles;
  }

  /// 刷新 — 从头加载
  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      _offset = 0;
      _hasMore = true;
      return _fetch(offset: 0);
    });
  }

  /// 加载更多 — 追加下一批
  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || !_hasMore) return;

    final ideaService = ref.read(ideaServiceProvider);
    try {
      final res = await ideaService.getExplore(
        offset: _offset,
        query: _filters.query,
        sort: _filters.sort,
        licenseCode: _filters.licenseCode,
        allowFork: _filters.allowFork,
        source: _filters.source,
      );
      _offset += res.circles.length;
      _hasMore = res.hasMore;
      state = AsyncData([...current, ...res.circles]);
    } catch (e, st) {
      // 加载更多失败时不清空已有数据，仅记录错误
      state = AsyncError(e, st);
    }
  }

  bool get hasMore => _hasMore;

  /// 发布新点子，返回新点子 ID（用于跳转详情）
  Future<String> createIdea(String content) async {
    final ideaService = ref.read(ideaServiceProvider);
    final res = await ideaService.createIdea(content);
    // 刷新探索列表（新点子会出现）
    await refresh();
    return res.id;
  }
}

/// 探索页 Provider — 主页圆圈列表
final exploreProvider =
    AsyncNotifierProvider<ExploreNotifier, List<CircleData>>(
        ExploreNotifier.new);
