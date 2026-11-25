import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';
import '../providers/idea_detail_provider.dart';

class PublishIdeaScreen extends ConsumerStatefulWidget {
  final String ideaId;

  const PublishIdeaScreen({super.key, required this.ideaId});

  @override
  ConsumerState<PublishIdeaScreen> createState() => _PublishIdeaScreenState();
}

class _PublishIdeaScreenState extends ConsumerState<PublishIdeaScreen> {
  String _licenseCode = 'attribution';
  bool _allowFork = false;
  bool _confirmTerms = false;
  bool _submitting = false;
  final _customLicenseController = TextEditingController();

  @override
  void dispose() {
    _customLicenseController.dispose();
    super.dispose();
  }

  bool get _supportsDerivatives =>
      _licenseCode == 'attribution_adaptation' || _licenseCode == 'custom';

  Future<void> _publish() async {
    if (!_confirmTerms) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先确认授权条款')),
      );
      return;
    }
    if (_licenseCode == 'custom' &&
        _customLicenseController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请填写自定义授权说明')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      await ref.read(ideaServiceProvider).publishIdea(
            ideaId: widget.ideaId,
            visibility: 'public',
            licenseCode: _licenseCode,
            licenseCustomText: _licenseCode == 'custom'
                ? _customLicenseController.text.trim()
                : null,
            allowFork: _allowFork,
            confirmTerms: _confirmTerms,
          );
      ref.invalidate(ideaDetailProvider(widget.ideaId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('点子已公开发布')),
        );
        context.pop();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('发布设置')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text(
            '发布后，这个点子将对所有人公开。请确认你拥有发布权限，并选择其他人可以如何使用它。',
            style: TextStyle(height: 1.6),
          ),
          const SizedBox(height: 20),
          const Text('授权方式', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _licenseCode,
            decoration: const InputDecoration(border: OutlineInputBorder()),
            items: const [
              DropdownMenuItem(
                value: 'all_rights_reserved',
                child: Text('保留所有权利'),
              ),
              DropdownMenuItem(
                value: 'attribution',
                child: Text('署名使用，不允许改编'),
              ),
              DropdownMenuItem(
                value: 'attribution_adaptation',
                child: Text('署名并允许改编'),
              ),
              DropdownMenuItem(value: 'custom', child: Text('自定义授权')),
            ],
            onChanged: _submitting
                ? null
                : (value) {
                    if (value == null) return;
                    setState(() {
                      _licenseCode = value;
                      if (!_supportsDerivatives) _allowFork = false;
                    });
                  },
          ),
          if (_licenseCode == 'custom') ...[
            const SizedBox(height: 12),
            TextField(
              controller: _customLicenseController,
              minLines: 3,
              maxLines: 6,
              maxLength: 5000,
              decoration: const InputDecoration(
                labelText: '自定义授权说明',
                border: OutlineInputBorder(),
              ),
            ),
          ],
          const SizedBox(height: 12),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('允许他人 Fork / 碰撞 / 演化'),
            subtitle: const Text('只有选择允许改编的授权方式后才能开启'),
            value: _allowFork,
            onChanged: _submitting || !_supportsDerivatives
                ? null
                : (value) => setState(() => _allowFork = value),
          ),
          const Divider(height: 28),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: _confirmTerms,
            onChanged: _submitting
                ? null
                : (value) => setState(() => _confirmTerms = value ?? false),
            title: const Text('我确认拥有发布该创意的权利，并同意按上述授权方式公开'),
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _submitting ? null : _publish,
            child: _submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('确认公开发布'),
          ),
        ],
      ),
    );
  }
}
