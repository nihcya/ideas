import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/spark.dart';
import 'api_provider.dart';

/// 今日一点 Notifier — 管理今日题目状态
class SparkTodayNotifier extends AsyncNotifier<SparkToday> {
  @override
  Future<SparkToday> build() async {
    final sparkService = ref.read(sparkServiceProvider);
    return sparkService.getToday();
  }

  /// 刷新今日题目
  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(sparkServiceProvider).getToday());
  }

  /// 保存草稿
  Future<SparkDraft> saveDraft(String content) async {
    final sparkService = ref.read(sparkServiceProvider);
    final result = await sparkService.saveDraft(content);
    // 保存草稿后刷新状态（has_draft 会变为 true）
    await refresh();
    return result;
  }

  /// 提交今日一点
  Future<SparkSubmitResult> submit(String content) async {
    final sparkService = ref.read(sparkServiceProvider);
    final result = await sparkService.submit(content);
    // 提交后刷新状态（submitted 会变为 true）
    await refresh();
    return result;
  }
}

/// 今日一点 Provider
final sparkTodayProvider =
    AsyncNotifierProvider<SparkTodayNotifier, SparkToday>(
        SparkTodayNotifier.new);
