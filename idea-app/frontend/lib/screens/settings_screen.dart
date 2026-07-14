import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/auth_provider.dart';
import '../providers/settings_provider.dart';

/// 设置页
///
/// 四个分区：
/// 1. 通用 - 通知开关、深色模式（固定）
/// 2. 大模型配置 - API 地址 + API 密钥（OpenAI 兼容协议）
/// 3. 其他 - 关于、清除缓存
/// 4. 账号 - 退出登录
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  // 大模型配置控制器
  final _apiUrlController = TextEditingController();
  final _apiKeyController = TextEditingController();
  bool _obscureApiKey = true; // 密码模式默认隐藏
  bool _llmLoaded = false; // 防止重复初始化
  bool _savingLlm = false;
  String? _apiUrlError; // URL 格式校验错误

  @override
  void dispose() {
    _apiUrlController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  /// 校验 URL 格式：必须 http/https 开头且能解析
  String? _validateUrl(String v) {
    if (v.isEmpty) return null; // 允许空（清除配置）
    if (!v.startsWith('http://') && !v.startsWith('https://')) {
      return '需以 http:// 或 https:// 开头';
    }
    final uri = Uri.tryParse(v);
    if (uri == null || !uri.isAbsolute || uri.host.isEmpty) {
      return 'URL 格式不正确';
    }
    return null;
  }

  /// 初始化：从后端拉取已保存的配置
  Future<void> _loadLlmConfig() async {
    if (_llmLoaded) return;
    _llmLoaded = true;
    try {
      final settings = await ref.read(settingsProvider.future);
      if (!mounted) return;
      setState(() {
        _apiUrlController.text = settings.llmApiUrl;
        // API key 后端返回脱敏（sk-***1234），直接显示。用户修改时清空重输。
        _apiKeyController.text = settings.llmApiKey;
      });
    } catch (_) {
      // 静默失败，不影响页面其他分区
    }
  }

  Future<void> _saveLlmConfig() async {
    // 触发同步校验
    setState(() {
      _apiUrlError = _validateUrl(_apiUrlController.text.trim());
    });
    if (_apiUrlError != null) return;

    setState(() => _savingLlm = true);
    try {
      await ref.read(settingsProvider.notifier).saveLlmConfig(
            apiUrl: _apiUrlController.text.trim(),
            apiKey: _apiKeyController.text.trim(),
          );
      if (!mounted) return;
      // 重新拉取以拿到脱敏后的 key
      final fresh = await ref.read(settingsProvider.future);
      setState(() {
        _apiKeyController.text = fresh.llmApiKey;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('大模型配置已保存'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('保存失败：$e')),
      );
    } finally {
      if (mounted) setState(() => _savingLlm = false);
    }
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('退出登录'),
        content: const Text('确定要退出当前账号吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: const Color(0xFFFF5252)),
            child: const Text('退出'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(logoutActionProvider)();
    } catch (_) {}
    if (mounted) context.go('/auth');
  }

  @override
  Widget build(BuildContext context) {
    // 进入页面后异步加载 LLM 配置
    _loadLlmConfig();

    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListView(
        children: [
          const _SectionHeader('通用'),
          ListTile(
            title: const Text('深色模式'),
            subtitle: const Text('固定开启'),
            trailing: Switch(
              value: true,
              onChanged: null,
            ),
          ),

          // ===================== 大模型配置 =====================
          const _SectionHeader('大模型配置'),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.info_outline, size: 16, color: Color(0xFF9A9AA0)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    '配置后，碰撞、演化、审核将调用你自己的大模型。留空则使用服务器默认配置或 Mock 模式。',
                    style: TextStyle(
                      fontSize: 12,
                      color: const Color(0xFF9A9AA0),
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ---- API 地址 ----
                _FieldLabel(
                  '大模型 API 地址',
                  tooltip: 'OpenAI 兼容协议端点。\n'
                      'DeepSeek: https://api.deepseek.com/v1\n'
                      'OpenAI:   https://api.openai.com/v1\n'
                      'Kimi:     https://api.moonshot.cn/v1',
                ),
                TextField(
                  controller: _apiUrlController,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  decoration: InputDecoration(
                    hintText: 'https://api.deepseek.com/v1',
                    errorText: _apiUrlError,
                    border: const OutlineInputBorder(),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 14),
                  ),
                  onChanged: (v) {
                    setState(() {
                      _apiUrlError = _validateUrl(v.trim());
                    });
                  },
                ),
                const SizedBox(height: 16),
                // ---- API 密钥 ----
                _FieldLabel(
                  'API 密钥',
                  tooltip: '在大模型厂商控制台创建 API Key 后粘贴。\n'
                      '仅用于当前账号的 AI 调用，不会同步到其他设备。',
                ),
                TextField(
                  controller: _apiKeyController,
                  obscureText: _obscureApiKey,
                  keyboardType: TextInputType.visiblePassword,
                  autocorrect: false,
                  decoration: InputDecoration(
                    hintText: 'sk-...',
                    border: const OutlineInputBorder(),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 14),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscureApiKey
                            ? Icons.visibility_off_outlined
                            : Icons.visibility_outlined,
                      ),
                      onPressed: () {
                        setState(() {
                          _obscureApiKey = !_obscureApiKey;
                        });
                      },
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                // ---- 保存按钮 ----
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _savingLlm ? null : _saveLlmConfig,
                    icon: _savingLlm
                        ? const SizedBox(
                            height: 16,
                            width: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.save_outlined),
                    label: Text(_savingLlm ? '保存中...' : '保存配置'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),

          // ===================== 其他 =====================
          const _SectionHeader('其他'),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('关于'),
            subtitle: const Text('点子 v0.1.0 · 创意激发社区'),
            onTap: () {
              showAboutDialog(
                context: context,
                applicationName: '点子',
                applicationVersion: '0.1.0',
                applicationLegalese: '让一个点子出生',
              );
            },
          ),
          const Divider(height: 1, indent: 16),
          const _SectionHeader('账号'),
          ListTile(
            leading: const Icon(Icons.logout, color: Color(0xFFFF5252)),
            title: const Text('退出登录',
                style: TextStyle(color: Color(0xFFFF5252))),
            onTap: _logout,
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

/// 小节标题
class _SectionHeader extends StatelessWidget {
  final String text;
  const _SectionHeader(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
      child: Text(
        text,
        style: const TextStyle(
          color: Color(0xFF9A9AA0),
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

/// 字段标签 + 帮助提示（问号图标点击弹气泡）
class _FieldLabel extends StatelessWidget {
  final String text;
  final String tooltip;
  const _FieldLabel(this.text, {required this.tooltip});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Text(
            text,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: Color(0xFFE0E0E0),
            ),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: () {
              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: Text(text),
                  content: Text(tooltip),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('知道了'),
                    ),
                  ],
                ),
              );
            },
            child: const Icon(
              Icons.help_outline,
              size: 16,
              color: Color(0xFF9A9AA0),
            ),
          ),
        ],
      ),
    );
  }
}
