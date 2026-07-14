import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/idea.dart';
import '../models/vault.dart';
import '../providers/vault_provider.dart';
import '../widgets/circle_canvas.dart';

/// 个人仓库页：自己产生的（金边）+ 收集的（无边）
class VaultScreen extends ConsumerWidget {
  const VaultScreen({super.key});

  Future<void> _refresh(WidgetRef ref) async {
    await ref.read(vaultProvider.notifier).refresh();
  }

  void _onCircleTap(BuildContext context, String id) {
    HapticFeedback.selectionClick();
    context.push('/idea/$id');
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncVault = ref.watch(vaultProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('仓库')),
      body: RefreshIndicator(
        onRefresh: () => _refresh(ref),
        child: asyncVault.when(
          data: (vault) {
            final visibleCircles = vault.circles
                .where((c) => c.status != 'faded')
                .map((c) => CircleData(
                      id: c.id,
                      colorHex: c.colorHex,
                      sizeScore: c.sizeScore,
                      isOwn: c.borderStyle == 'gold-thin',
                      forkCount: 0,
                      borderStyle: c.borderStyle,
                      status: c.status,
                    ))
                .toList();
            return Column(
              children: [
                _StatsCard(stats: vault.stats),
                Expanded(
                  child: visibleCircles.isEmpty
                      ? ListView(
                          children: const [
                            SizedBox(height: 200),
                            Center(
                              child: Text(
                                '仓库还是空的，去探索捡几个吧',
                                style: TextStyle(color: Color(0xFF9A9AA0)),
                              ),
                            ),
                          ],
                        )
                      : CircleCanvas(
                          circles: visibleCircles,
                          onTap: (id) => _onCircleTap(context, id),
                          hasMore: vault.hasMore,
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
                  onPressed: () => _refresh(ref),
                  child: const Text('重试'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatsCard extends StatelessWidget {
  final VaultStats stats;
  const _StatsCard({required this.stats});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A1E),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          _statCell('自己产生', stats.produced, const Color(0xFFFFD700)),
          _divider(),
          _statCell('收集', stats.collected, const Color(0xFF4ECDC4)),
          _divider(),
          _statCell('被 Fork', stats.forkedByOthers, const Color(0xFFB5A8E8)),
        ],
      ),
    );
  }

  Widget _statCell(String label, int value, Color color) {
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
            style: const TextStyle(fontSize: 12, color: Color(0xFF9A9AA0)),
          ),
        ],
      ),
    );
  }

  Widget _divider() {
    return Container(
      width: 1,
      height: 32,
      color: const Color(0xFF2A2A2E),
    );
  }
}
