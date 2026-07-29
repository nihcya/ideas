import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/idea_detail_provider.dart';
import '../theme/app_theme.dart';

/// Fork 引导页：阅读原点子 → 写下你的联想
class ForkGuideScreen extends ConsumerStatefulWidget {
  final String parentId;
  const ForkGuideScreen({super.key, required this.parentId});

  @override
  ConsumerState<ForkGuideScreen> createState() => _ForkGuideScreenState();
}

class _ForkGuideScreenState extends ConsumerState<ForkGuideScreen> {
  final _ctrl = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _confirmFork() async {
    final content = _ctrl.text.trim();
    if (content.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('写下你的联想')));
      return;
    }
    setState(() => _submitting = true);
    try {
      final newId = await ref
          .read(ideaDetailProvider(widget.parentId).notifier)
          .forkIdea(content);
      HapticFeedback.heavyImpact();
      if (mounted) context.pushReplacement('/idea/$newId');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final asyncDetail = ref.watch(ideaDetailProvider(widget.parentId));
    final colors = AppColors.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fork'),
        actions: [
          TextButton(
            onPressed: _submitting ? null : _confirmFork,
            child: _submitting
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('确认 Fork'),
          ),
        ],
      ),
      body: asyncDetail.when(
        data: (detail) {
          return Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colors.surface,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 14,
                            height: 14,
                            decoration: BoxDecoration(
                              color: _parseColor(detail.colorHex),
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '来自 @${detail.author.username}',
                            style: TextStyle(
                              color: colors.textSecondary,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        detail.content,
                        style: TextStyle(
                          color: colors.textSecondary,
                          fontSize: 15,
                          height: 1.6,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  '这个点子让你想到了什么？',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: TextField(
                    controller: _ctrl,
                    maxLength: 300,
                    maxLines: null,
                    expands: true,
                    autofocus: true,
                    style: const TextStyle(fontSize: 16, height: 1.6),
                    decoration: const InputDecoration(
                      hintText: '写下你的联想...',
                      alignLabelWithHint: true,
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: Text(
                    '${_ctrl.text.length}/300',
                    style: TextStyle(
                      color: colors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => Center(child: Text('加载原点子失败：$e')),
      ),
    );
  }

  Color _parseColor(String hex) {
    final s = hex.replaceFirst('#', '');
    return Color(int.parse('FF$s', radix: 16));
  }
}
