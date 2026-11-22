import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/collaboration_service.dart';
import '../services/evolve_service.dart';
import '../services/idea_service.dart';
import '../services/notification_service.dart';
import '../services/settings_service.dart';
import '../services/spark_service.dart';
import '../services/user_service.dart';
import '../services/vault_service.dart';
import 'auth_provider.dart';

final apiClientProvider = Provider<Dio>((ref) {
  return createApiClient(
    onUnauthorized: () {
      ref.read(authStateProvider.notifier).setUnauthenticated();
    },
  );
});

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref.read(apiClientProvider));
});
final ideaServiceProvider = Provider<IdeaService>((ref) {
  return IdeaService(ref.read(apiClientProvider));
});
final collaborationServiceProvider = Provider<CollaborationService>((ref) {
  return CollaborationService(ref.read(apiClientProvider));
});
final evolveServiceProvider = Provider<EvolveService>((ref) {
  return EvolveService(ref.read(apiClientProvider));
});
final vaultServiceProvider = Provider<VaultService>((ref) {
  return VaultService(ref.read(apiClientProvider));
});
final sparkServiceProvider = Provider<SparkService>((ref) {
  return SparkService(ref.read(apiClientProvider));
});
final userServiceProvider = Provider<UserService>((ref) {
  return UserService(ref.read(apiClientProvider));
});
final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService(ref.read(apiClientProvider));
});
final settingsServiceProvider = Provider<SettingsService>((ref) {
  return SettingsService(ref.read(apiClientProvider));
});
