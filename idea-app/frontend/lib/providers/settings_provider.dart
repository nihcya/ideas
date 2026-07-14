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
}

final settingsProvider =
    AsyncNotifierProvider<SettingsNotifier, UserSettings>(SettingsNotifier.new);
