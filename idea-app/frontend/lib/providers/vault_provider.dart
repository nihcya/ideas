import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/vault.dart';
import 'api_provider.dart';

/// 仓库页 Notifier — 管理仓库圆圈列表 + 统计数据
class VaultNotifier extends AsyncNotifier<VaultResponse> {
  @override
  Future<VaultResponse> build() async {
    final vaultService = ref.read(vaultServiceProvider);
    return vaultService.getVault();
  }

  /// 刷新仓库数据
  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
        () => ref.read(vaultServiceProvider).getVault());
  }

  /// 收集点子到仓库
  Future<void> collectIdea(String ideaId) async {
    final vaultService = ref.read(vaultServiceProvider);
    await vaultService.collectIdea(ideaId);
    await refresh();
  }

  /// 从仓库移出点子
  Future<void> removeFromVault(String ideaId) async {
    final vaultService = ref.read(vaultServiceProvider);
    await vaultService.removeFromVault(ideaId);
    await refresh();
  }
}

/// 仓库 Provider
final vaultProvider =
    AsyncNotifierProvider<VaultNotifier, VaultResponse>(VaultNotifier.new);
