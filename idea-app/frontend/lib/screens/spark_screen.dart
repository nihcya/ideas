import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/spark.dart';
import '../providers/spark_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/countdown_ring_painter.dart';

/// 今日一点页：每日一题 + 3 分钟倒计时 + 草稿自动保存
class SparkScreen extends ConsumerStatefulWidget {
  const SparkScreen({super.key});

  @override
  ConsumerState<SparkScreen> createState() => _SparkScreenState();
}

class _SparkScreenState extends ConsumerState<SparkScreen>
    with SingleTickerProviderStateMixin {
  final _ctrl = TextEditingController();
  Timer? _countdownTimer;
  Timer? _debounceTimer;
  int _remaining = 180;
  int _totalDuration = 180;
  bool _initialized = false;
  bool _savingDraft = false;
  bool _submitting = false;
  bool _draftSaved = false;
  bool _countdownEnded = false;
  String? _submittedContent;

  /// 题目渐显动画控制器。
  late final AnimationController _fadeController;
  late final Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeIn,
    );
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _debounceTimer?.cancel();
    _ctrl.dispose();
    _fadeController.dispose();
    super.dispose();
  }

  void _initFromData(SparkToday data) {
    if (_initialized) return;
    _initialized = true;
    _remaining = data.durationSeconds;
    _totalDuration = data.durationSeconds;
    if (data.hasDraft) {
      _draftSaved = true;
      // 草稿回填：将后端返回的草稿内容填入输入框
      if (data.draftContent != null && data.draftContent!.isNotEmpty) {
        _ctrl.text = data.draftContent!;
      }
    }
    _startCountdown();
    // 触发题目渐显动画
    _fadeController.forward();
  }

  void _startCountdown() {
    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      setState(() {
        if (_remaining <= 0) {
          if (!_countdownEnded) {
            _countdownEnded = true;
            t.cancel();
            _autoSaveDraft();
          }
        } else {
          _remaining -= 1;
          if (_remaining == 0 && !_countdownEnded) {
            _countdownEnded = true;
            _autoSaveDraft();
          }
        }
      });
    });
  }

  void _onTextChanged(String _) {
    setState(() {});
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(seconds: 2), () {
      _saveDraft(showHint: false);
    });
  }

  Future<void> _autoSaveDraft() async {
    if (_ctrl.text.trim().isEmpty) return;
    await _saveDraft(showHint: true);
  }

  Future<void> _saveDraft({required bool showHint}) async {
    if (_ctrl.text.trim().isEmpty) return;
    setState(() => _savingDraft = true);
    try {
      await ref.read(sparkTodayProvider.notifier).saveDraft(_ctrl.text);
      if (mounted) {
        setState(() {
          _savingDraft = false;
          _draftSaved = true;
        });
        if (showHint && mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('📝 草稿已保存。保留到今晚 23:59，明天就清空啦，记得回来完成！'),
              duration: Duration(seconds: 3),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) setState(() => _savingDraft = false);
    }
  }

  Future<void> _submit() async {
    final content = _ctrl.text.trim();
    if (content.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('写点什么再提交吧')),
      );
      return;
    }
    setState(() => _submitting = true);
    try {
      final result =
          await ref.read(sparkTodayProvider.notifier).submit(content);
      _countdownTimer?.cancel();
      _debounceTimer?.cancel();
      if (mounted) {
        setState(() => _submittedContent = content);
        context.pushReplacement('/idea/${result.id}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String _formatCountdown(int s) {
    final m = (s ~/ 60).toString().padLeft(2, '0');
    final sec = (s % 60).toString().padLeft(2, '0');
    return '$m:$sec';
  }

  @override
  Widget build(BuildContext context) {
    final asyncSpark = ref.watch(sparkTodayProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('今日一点')),
      body: asyncSpark.when(
        data: (spark) {
          if (spark.submitted) {
            return _SubmittedView(spark: spark, content: _submittedContent);
          }
          _initFromData(spark);
          return _buildInputView(context, spark);
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => _ErrorView(
          message: e.toString(),
          onRetry: () => ref.invalidate(sparkTodayProvider),
        ),
      ),
    );
  }

  Widget _buildInputView(BuildContext context, SparkToday spark) {
    final colors = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 16),
          FadeTransition(
            opacity: _fadeAnimation,
            child: Text(
              spark.question,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                height: 1.5,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox(
                width: 20,
                height: 20,
                child: CustomPaint(
                  painter: CountdownRingPainter(
                    progress: _totalDuration > 0
                        ? _remaining / _totalDuration
                        : 0,
                    color: _remaining <= 30 ? colors.error : colors.gold,
                  ),
                ),
              ),
              const SizedBox(width: 6),
              Text(
                _formatCountdown(_remaining),
                style: TextStyle(
                  fontSize: 14,
                  color: _remaining <= 30 ? colors.error : colors.textSecondary,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              if (_savingDraft) ...[
                const SizedBox(width: 12),
                const SizedBox(
                  width: 10,
                  height: 10,
                  child: CircularProgressIndicator(strokeWidth: 1.5),
                ),
                const SizedBox(width: 4),
                Text(
                  '保存中',
                  style: TextStyle(fontSize: 11, color: colors.textSecondary),
                ),
              ] else if (_draftSaved) ...[
                const SizedBox(width: 12),
                Icon(Icons.check, size: 12, color: colors.success),
                const SizedBox(width: 4),
                Text(
                  '草稿已保存',
                  style: TextStyle(fontSize: 11, color: colors.success),
                ),
              ],
            ],
          ),
          const SizedBox(height: 24),
          Expanded(
            child: TextField(
              controller: _ctrl,
              maxLength: 300,
              maxLines: null,
              expands: true,
              style: const TextStyle(fontSize: 16, height: 1.6),
              decoration: const InputDecoration(
                hintText: '在这里写下你的想法...',
                alignLabelWithHint: true,
              ),
              onChanged: _onTextChanged,
            ),
          ),
          const SizedBox(height: 8),
          ElevatedButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.black),
                  )
                : const Text('提交'),
          ),
        ],
      ),
    );
  }
}

class _SubmittedView extends StatelessWidget {
  final SparkToday spark;
  final String? content;
  const _SubmittedView({required this.spark, this.content});

  @override
  Widget build(BuildContext context) {
    final colors = AppColors.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: colors.gold.withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.check, color: colors.gold, size: 44),
            ),
            const SizedBox(height: 24),
            const Text(
              '今日已完成',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Text(
              spark.question,
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 24),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colors.surface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                (content == null || content!.isEmpty)
                    ? '（无内容）'
                    : content!,
                style: const TextStyle(fontSize: 15, height: 1.6),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              '明天再来捕捉新的灵感',
              style: TextStyle(color: colors.textSecondary, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final colors = AppColors.of(context);
    final expired = message.contains('expired') || message.contains('410');
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              expired ? Icons.schedule_outlined : Icons.error_outline,
              size: 56,
              color: colors.textSecondary,
            ),
            const SizedBox(height: 16),
            Text(
              expired ? '今日一点已过期，明天再来吧' : '加载失败：$message',
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.textSecondary),
            ),
            if (!expired) ...[
              const SizedBox(height: 16),
              TextButton(onPressed: onRetry, child: const Text('重试')),
            ],
          ],
        ),
      ),
    );
  }
}
