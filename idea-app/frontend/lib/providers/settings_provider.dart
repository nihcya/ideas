import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/settings_service.dart';
import 'api_provider.dart';

/// 设置服务 Provider
final settingsServiceProvider = Provider<SettingsService>((ref) {
  return SettingsService(ref.read(apiClientProvider));
});

/// 设置状态：使用 AsyncNotifier 管理异步加载 + 保存
class SettingsNotifier extends AsyncNotifier<UserSettings> {
  @override
  Future<UserSettings> build() async {
    return ref.read(settingsServiceProvider).getSettings();
  }

  /// 保存大模型配置
  /// [apiUrl] 为 null 表示不修改；为空字符串表示清除
  /// [apiKey] 同理
  Future<void> saveLlmConfig({
    String? apiUrl,
    String? apiKey,
  }) async {
    final service = ref.read(settingsServiceProvider);
    await service.updateSettings(
      llmApiUrl: apiUrl,
      llmApiKey: apiKey,
    );
    // 重新拉取以拿到脱敏后的 key
    final fresh = await service.getSettings();
    state = AsyncData(fresh);
  }

  /// 切换暗色模式（S2：dark_mode 接入主题）
  Future<void> saveDarkMode(bool darkMode) async {
    final service = ref.read(settingsServiceProvider);
    await service.updateSettings(darkMode: darkMode);
    // 乐观更新本地状态，主题立即响应
    final current = state.value;
    if (current != null) {
      state = AsyncData(UserSettings(
        darkMode: darkMode,
        forkable: current.forkable,
        username: current.username,
        isAdmin: current.isAdmin,
        bio: current.bio,
        llmApiUrl: current.llmApiUrl,
        llmApiKey: current.llmApiKey,
        llmApiKeyConfigured: current.llmApiKeyConfigured,
      ));
    }
  }
}

final settingsProvider =
    AsyncNotifierProvider<SettingsNotifier, UserSettings>(SettingsNotifier.new);
