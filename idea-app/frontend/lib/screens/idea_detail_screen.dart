import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/idea.dart';
import '../providers/idea_detail_provider.dart';
import '../providers/vault_provider.dart';
import '../widgets/evolve_menu.dart';
import '../widgets/lineage_tree.dart';

/// 点子详情页：大圆圈 + 内容 + 谱系图 + 操作栏
class IdeaDetailScreen extends ConsumerStatefulWidget {
  final String ideaId;
  const IdeaDetailScreen({super.key, required this.ideaId});

  @override
  ConsumerState<IdeaDetailScreen> createState() => _IdeaDetailScreenState();
}

class _IdeaDetailScreenState extends ConsumerState<IdeaDetailScreen> {
  bool _collecting = false;

  @override
  Widget build(BuildContext context) {
    final asyncDetail = ref.watch(ideaDetailProvider(widget.ideaId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('点子'),
        // 当导航栈无可返回页面时（如从每日一题 pushReplacement 跳转来），
        // 手动提供返回按钮，回到探索页
        leading: Navigator.canPop(context)
            ? null // 有上一页时用默认返回按钮
            : IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => context.go('/explore'),
              ),
      ),
      body: asyncDetail.when(
        data: (detail) => _DetailBody(
          detail: detail,
          onCircleTap: (id) => context.push('/idea/$id'),
          onFork: () => context.push('/fork/${widget.ideaId}'),
          onToggleCollect: _toggleCollect,
          onEvolveMenu: () => _showEvolveMenu(context),
          collecting: _collecting,
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('加载失败：$e'),
              const SizedBox(height: 16),
              TextButton(
                onPressed: () => ref.invalidate(
                    ideaDetailProvider(widget.ideaId)),
                child: const Text('重试'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _toggleCollect(bool currentlyInVault) async {
    HapticFeedback.selectionClick();
    setState(() => _collecting = true);
    try {
      final notifier =
          ref.read(ideaDetailProvider(widget.ideaId).notifier);
      if (currentlyInVault) {
        await notifier.removeFromVault();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('已移出仓库')),
          );
        }
      } else {
        await notifier.collectIdea();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('已收集到仓库')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _collecting = false);
    }
  }

  void _showEvolveMenu(BuildContext context) {
    HapticFeedback.mediumImpact();
    showEvolveMenu(
      context,
      onCollide: () => _startCollide(context),
      onEvolve: () => _startEvolve(context),
    );
  }

  // —— 碰撞流程 ——
  Future<void> _startCollide(BuildContext context) async {
    HapticFeedback.mediumImpact();
    final otherId = await _pickSecondIdea(context);
    if (otherId == null || !mounted) return;
    if (otherId == widget.ideaId) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('不能和自身碰撞，换一个吧')),
      );
      return;
    }

    // 调用碰撞 API 获取 3 个建议
    CollideResponse? resp;
    try {
      resp = await ref
          .read(ideaDetailProvider(widget.ideaId).notifier)
          .collide(otherId);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('碰撞失败：$e')));
      }
      return;
    }
    if (!mounted) return;

    // 用户选一个建议
    final picked = await _pickSuggestion(context, resp.suggestions);
    if (picked == null || !mounted) return;

    // 编辑后确认
    final confirmed = await _editAndConfirm(
      context,
      initialContent: picked.content,
      title: '确认碰撞结果',
    );
    if (confirmed == null || !mounted) return;

    try {
      final newId = await ref
          .read(ideaDetailProvider(widget.ideaId).notifier)
          .collideConfirm(otherId, confirmed, true);
      if (mounted) context.pushReplacement('/idea/$newId');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('确认失败：$e')));
      }
    }
  }

  // —— 演化流程 ——
  Future<void> _startEvolve(BuildContext context) async {
    HapticFeedback.mediumImpact();
    final angle = await _pickSamperAngle(context);
    if (angle == null || !mounted) return;

    EvolveResponse? resp;
    try {
      resp = await ref
          .read(ideaDetailProvider(widget.ideaId).notifier)
          .evolve(angle);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('演化失败：$e')));
      }
      return;
    }
    if (!mounted) return;

    final picked = await _pickVariant(context, resp.variants);
    if (picked == null || !mounted) return;

    final confirmed = await _editAndConfirm(
      context,
      initialContent: picked.content,
      title: '确认演化变体',
    );
    if (confirmed == null || !mounted) return;

    try {
      final newId = await ref
          .read(ideaDetailProvider(widget.ideaId).notifier)
          .evolveConfirm(angle, confirmed, true);
      if (mounted) context.pushReplacement('/idea/$newId');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('确认失败：$e')));
      }
    }
  }

  // 从仓库选第二个点子
  Future<String?> _pickSecondIdea(BuildContext context) async {
    final vault = ref.read(vaultProvider).maybeWhen(
          data: (v) => v,
          orElse: () => null,
        );
    final circles = vault?.circles
            .where((c) => c.status != 'faded' && c.id != widget.ideaId)
            .toList() ??
        [];
    if (circles.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('仓库里没有可碰撞的点子，先去收集一些吧')),
      );
      return null;
    }
    return showModalBottomSheet<String>(
      context: context,
      backgroundColor: const Color(0xFF1A1A1E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  '选一个点子来碰撞',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ),
              const Divider(height: 1, color: Color(0xFF2A2A2E)),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: circles.length,
                  itemBuilder: (_, i) {
                    final c = circles[i];
                    return ListTile(
                      leading: Container(
                        width: 28,
                        height: 28,
                        decoration: BoxDecoration(
                          color: _parseColor(c.colorHex),
                          shape: BoxShape.circle,
                          border: c.borderStyle == 'gold-thin'
                              ? Border.all(
                                  color: const Color(0xFFFFD700), width: 2)
                              : null,
                        ),
                      ),
                      title: Text(
                        '点子 ${c.id.substring(0, 6)}',
                        style: const TextStyle(fontSize: 14),
                      ),
                      onTap: () => Navigator.pop(ctx, c.id),
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // 选碰撞建议
  Future<CollideSuggestion?> _pickSuggestion(
      BuildContext context, List<CollideSuggestion> suggestions) async {
    return showModalBottomSheet<CollideSuggestion>(
      context: context,
      backgroundColor: const Color(0xFF1A1A1E),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'AI 生成的碰撞方案',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ),
              const Divider(height: 1, color: Color(0xFF2A2A2E)),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: suggestions.length,
                  itemBuilder: (_, i) {
                    final s = suggestions[i];
                    return ListTile(
                      title: Text(
                        _suggestionTypeLabel(s.type),
                        style: const TextStyle(
                          color: Color(0xFFFFD700),
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      subtitle: Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          s.content,
                          style: const TextStyle(
                              fontSize: 14, color: Color(0xFFF5F5F7)),
                        ),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 10),
                      onTap: () => Navigator.pop(ctx, s),
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // 选演化变体
  Future<EvolveVariant?> _pickVariant(
      BuildContext context, List<EvolveVariant> variants) async {
    return showModalBottomSheet<EvolveVariant>(
      context: context,
      backgroundColor: const Color(0xFF1A1A1E),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'AI 生成的演化变体',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ),
              const Divider(height: 1, color: Color(0xFF2A2A2E)),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: variants.length,
                  itemBuilder: (_, i) {
                    final v = variants[i];
                    return ListTile(
                      title: Text(
                        _distanceLabel(v.distance),
                        style: const TextStyle(
                          color: Color(0xFFB5A8E8),
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      subtitle: Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          v.content,
                          style: const TextStyle(
                              fontSize: 14, color: Color(0xFFF5F5F7)),
                        ),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 10),
                      onTap: () => Navigator.pop(ctx, v),
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // SAMPER 角度选择
  Future<String?> _pickSamperAngle(BuildContext context) async {
    const angles = [
      ('substitute', 'S · 替代', '这个点子里什么可以被替换？'),
      ('adapt', 'A · 适应', '能从其他领域借鉴什么？'),
      ('modify', 'M · 修改', '放大或缩小某个方面？'),
      ('put_to_other_use', 'P · 其他用途', '这个点子还能用在哪里？'),
      ('eliminate', 'E · 消除', '去掉什么会让它更好？'),
      ('reverse', 'R · 反转', '反过来想会怎样？'),
    ];
    return showModalBottomSheet<String>(
      context: context,
      backgroundColor: const Color(0xFF1A1A1E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  '选一个 SAMPER 角度',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ),
              const Divider(height: 1, color: Color(0xFF2A2A2E)),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: angles.length,
                  itemBuilder: (_, i) {
                    final a = angles[i];
                    return ListTile(
                      title: Text(a.$2,
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text(a.$3,
                          style: const TextStyle(
                              fontSize: 12, color: Color(0xFF9A9AA0))),
                      onTap: () {
                        HapticFeedback.lightImpact();
                        Navigator.pop(ctx, a.$1);
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // 编辑并确认内容
  Future<String?> _editAndConfirm(
    BuildContext context, {
    required String initialContent,
    required String title,
  }) async {
    final ctrl = TextEditingController(text: initialContent);
    return showDialog<String>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1A1A1E),
          title: Text(title),
          content: SingleChildScrollView(
            child: TextField(
              controller: ctrl,
              maxLength: 300,
              maxLines: 8,
              style: const TextStyle(fontSize: 14),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确认'),
            ),
          ],
        );
      },
    );
  }

  Color _parseColor(String hex) {
    final s = hex.replaceFirst('#', '');
    return Color(int.parse('FF$s', radix: 16));
  }

  String _suggestionTypeLabel(String type) {
    switch (type) {
      case 'practical':
        return '实用型';
      case 'cross_domain':
        return '跨界型';
      case 'unconventional':
        return '反常规型';
      default:
        return type;
    }
  }

  String _distanceLabel(String distance) {
    switch (distance) {
      case 'near':
        return '近 · 微调';
      case 'medium':
        return '中 · 明显变形';
      case 'bold':
        return '远 · 大胆重构';
      default:
        return distance;
    }
  }
}

class _DetailBody extends StatelessWidget {
  final IdeaDetail detail;
  final void Function(String) onCircleTap;
  final VoidCallback onFork;
  final void Function(bool currentlyInVault) onToggleCollect;
  final VoidCallback onEvolveMenu;
  final bool collecting;

  const _DetailBody({
    required this.detail,
    required this.onCircleTap,
    required this.onFork,
    required this.onToggleCollect,
    required this.onEvolveMenu,
    required this.collecting,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 100),
          children: [
            // 顶部大圆圈
            Center(
              child: Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  color: _parseColor(detail.colorHex),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: _parseColor(detail.colorHex).withValues(alpha: 0.3),
                      blurRadius: 30,
                      spreadRadius: 2,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            // 内容
            Text(
              detail.content,
              style: const TextStyle(fontSize: 16, height: 1.7),
            ),
            const SizedBox(height: 24),
            // 作者信息
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1A1E),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 18,
                    backgroundColor: const Color(0xFFFFD700),
                    child: Text(
                      detail.author.username.isNotEmpty
                          ? detail.author.username[0].toUpperCase()
                          : '?',
                      style: const TextStyle(
                          color: Colors.black, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          detail.author.username,
                          style: const TextStyle(
                              fontSize: 14, fontWeight: FontWeight.w600),
                        ),
                        if (detail.author.bio.isNotEmpty)
                          Text(
                            detail.author.bio,
                            style: const TextStyle(
                                fontSize: 12, color: Color(0xFF9A9AA0)),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            // 时间 + fork 数
            Row(
              children: [
                const Icon(Icons.access_time,
                    size: 14, color: Color(0xFF9A9AA0)),
                const SizedBox(width: 4),
                Text(
                  _formatTime(detail.createdAt),
                  style: const TextStyle(
                      fontSize: 12, color: Color(0xFF9A9AA0)),
                ),
                const SizedBox(width: 16),
                const Icon(Icons.call_split,
                    size: 14, color: Color(0xFF9A9AA0)),
                const SizedBox(width: 4),
                Text(
                  '${detail.forkCount} 次 fork',
                  style: const TextStyle(
                      fontSize: 12, color: Color(0xFF9A9AA0)),
                ),
              ],
            ),
            const SizedBox(height: 28),
            // 谱系图
            if (detail.lineage.parents.isNotEmpty ||
                detail.lineage.children.isNotEmpty) ...[
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: Text(
                  '谱系',
                  style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF9A9AA0)),
                ),
              ),
              LineageTree(
                lineage: detail.lineage,
                onTap: onCircleTap,
              ),
              const SizedBox(height: 24),
            ],
          ],
        ),
        // 底部操作栏
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: Container(
            decoration: BoxDecoration(
              color: const Color(0xFF0E0E10),
              border: Border(
                  top: BorderSide(color: const Color(0xFF2A2A2E), width: 1)),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: SafeArea(
              top: false,
              child: Row(
                children: [
                  Expanded(
                    child: _ActionButton(
                      icon: Icons.call_split,
                      label: 'Fork',
                      onTap: onFork,
                    ),
                  ),
                  Expanded(
                    child: _ActionButton(
                      icon: detail.isInVault
                          ? Icons.bookmark
                          : Icons.bookmark_border,
                      label: detail.isInVault ? '已收集' : '收集',
                      loading: collecting,
                      onTap: () => onToggleCollect(detail.isInVault),
                    ),
                  ),
                  Expanded(
                    child: _ActionButton(
                      icon: Icons.auto_awesome_outlined,
                      label: '演化',
                      onTap: onEvolveMenu,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Color _parseColor(String hex) {
    final s = hex.replaceFirst('#', '');
    return Color(int.parse('FF$s', radix: 16));
  }

  String _formatTime(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool loading;
  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: loading ? null : onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            loading
                ? const SizedBox(
                    height: 22,
                    width: 22,
                    child:
                        CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(icon, color: const Color(0xFFFFD700)),
            const SizedBox(height: 4),
            Text(
              label,
              style: const TextStyle(
                fontSize: 11,
                color: Color(0xFFFFD700),
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
