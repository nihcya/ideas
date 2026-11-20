import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/idea.dart';
import 'api_provider.dart';
import 'vault_provider.dart';

/// 点子详情 Notifier — family，按 ideaId 获取详情
///
/// 同时承载与该点子相关的操作：Fork / 收集 / 碰撞 / 演化。
/// 所有 mutation 方法返回新点子 ID（如适用），便于 UI 跳转。
class IdeaDetailNotifier extends FamilyAsyncNotifier<IdeaDetail, String> {
  @override
  Future<IdeaDetail> build(String ideaId) async {
    final ideaService = ref.read(ideaServiceProvider);
    return ideaService.getIdeaDetail(ideaId);
  }

  /// 刷新详情
  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(ideaServiceProvider).getIdeaDetail(arg));
  }

  /// Fork 当前点子，返回新点子 ID
  Future<String> forkIdea(String content) async {
    final ideaService = ref.read(ideaServiceProvider);
    final res = await ideaService.forkIdea(parentId: arg, content: content);
    // 刷新当前详情（fork_count 会增加）
    await refresh();
    return res.id;
  }

  /// 收集当前点子到仓库
  Future<void> collectIdea() async {
    final vaultService = ref.read(vaultServiceProvider);
    await vaultService.collectIdea(arg);
    // 同步刷新仓库
    ref.invalidate(vaultProvider);
    // 更新本地状态：isInVault = true
    final current = state.valueOrNull;
    if (current != null) {
      state = AsyncData(IdeaDetail(
        id: current.id,
        content: current.content,
        colorHex: current.colorHex,
        author: current.author,
        createdAt: current.createdAt,
        forkCount: current.forkCount,
        isInVault: true,
        lineage: current.lineage,
        publicationStatus: current.publicationStatus,
        visibility: current.visibility,
        licenseCode: current.licenseCode,
        licenseVersion: current.licenseVersion,
        isForkable: current.isForkable,
      ));
    }
  }

  /// 从仓库移出
  Future<void> removeFromVault() async {
    final vaultService = ref.read(vaultServiceProvider);
    await vaultService.removeFromVault(arg);
    ref.invalidate(vaultProvider);
    final current = state.valueOrNull;
    if (current != null) {
      state = AsyncData(IdeaDetail(
        id: current.id,
        content: current.content,
        colorHex: current.colorHex,
        author: current.author,
        createdAt: current.createdAt,
        forkCount: current.forkCount,
        isInVault: false,
        lineage: current.lineage,
        publicationStatus: current.publicationStatus,
        visibility: current.visibility,
        licenseCode: current.licenseCode,
        licenseVersion: current.licenseVersion,
        isForkable: current.isForkable,
      ));
    }
  }

  /// 碰撞当前点子与另一个点子，AI 生成 3 个方案
  Future<CollideResponse> collide(String otherId) async {
    final evolveService = ref.read(evolveServiceProvider);
    return evolveService.collide(ideaAId: arg, ideaBId: otherId);
  }

  /// 碰撞确认 — 用户选定方案后入库，返回新点子 ID
  Future<String> collideConfirm(
    String otherId,
    String content,
    bool aiAssisted,
  ) async {
    final evolveService = ref.read(evolveServiceProvider);
    final res = await evolveService.collideConfirm(
      ideaAId: arg,
      ideaBId: otherId,
      content: content,
      aiAssisted: aiAssisted,
    );
    ref.invalidate(vaultProvider);
    return res.id;
  }

  /// 演化当前点子，选 SAMPER 角度，AI 生成 3 个变体
  Future<EvolveResponse> evolve(String angle) async {
    final evolveService = ref.read(evolveServiceProvider);
    return evolveService.evolve(ideaId: arg, angle: angle);
  }

  /// 演化确认 — 用户选定变体后入库，返回新点子 ID
  Future<String> evolveConfirm(
    String angle,
    String content,
    bool aiAssisted,
  ) async {
    final evolveService = ref.read(evolveServiceProvider);
    final res = await evolveService.evolveConfirm(
      parentId: arg,
      angle: angle,
      content: content,
      aiAssisted: aiAssisted,
    );
    ref.invalidate(vaultProvider);
    return res.id;
  }
}

/// 点子详情 Provider — family，传入 ideaId
///
/// 用法：`ref.watch(ideaDetailProvider(ideaId))`
final ideaDetailProvider =
    AsyncNotifierProvider.family<IdeaDetailNotifier, IdeaDetail, String>(
        IdeaDetailNotifier.new);
