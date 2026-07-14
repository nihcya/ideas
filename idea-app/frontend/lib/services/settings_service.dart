import 'package:dio/dio.dart';

import 'api_client.dart';

/// 用户设置（含大模型配置）
class UserSettings {
  final bool darkMode;
  final bool forkable;
  final String username;
  final String bio;
  final String llmApiUrl;
  final String llmApiKey; // 后端已脱敏（sk-***1234）
  final bool llmApiKeyConfigured;

  const UserSettings({
    required this.darkMode,
    required this.forkable,
    required this.username,
    required this.bio,
    required this.llmApiUrl,
    required this.llmApiKey,
    required this.llmApiKeyConfigured,
  });

  factory UserSettings.fromJson(Map<String, dynamic> json) {
    return UserSettings(
      darkMode: json['dark_mode'] as bool? ?? false,
      forkable: json['forkable'] as bool? ?? true,
      username: json['username'] as String? ?? '',
      bio: json['bio'] as String? ?? '',
      llmApiUrl: json['llm_api_url'] as String? ?? '',
      llmApiKey: json['llm_api_key'] as String? ?? '',
      llmApiKeyConfigured: json['llm_api_key_configured'] as bool? ?? false,
    );
  }
}

/// 设置服务：GET / PUT /settings
class SettingsService {
  final Dio _dio;
  SettingsService(this._dio);

  /// 读取当前用户设置
  Future<UserSettings> getSettings() async {
    try {
      final res = await _dio.get('/settings');
      return UserSettings.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }

  /// 更新设置（仅传需要修改的字段）
  Future<void> updateSettings({
    bool? darkMode,
    bool? forkable,
    String? bio,
    String? llmApiUrl,
    String? llmApiKey,
  }) async {
    try {
      final body = <String, dynamic>{};
      if (darkMode != null) body['dark_mode'] = darkMode;
      if (forkable != null) body['forkable'] = forkable;
      if (bio != null) body['bio'] = bio;
      if (llmApiUrl != null) body['llm_api_url'] = llmApiUrl;
      if (llmApiKey != null) body['llm_api_key'] = llmApiKey;
      await _dio.put('/settings', data: body);
    } on DioException catch (e) {
      throw toApiException(e);
    }
  }
}
