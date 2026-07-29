import 'dart:developer';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'connection_provider.dart';
import 'settings_provider.dart';

class UserModel {
  final String id;
  final String? email;
  final String displayName;
  final String? avatarUrl;
  final String authType;

  UserModel({
    required this.id,
    this.email,
    required this.displayName,
    this.avatarUrl,
    required this.authType,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String? ?? 'user',
      email: json['email'] as String?,
      displayName: json['display_name'] as String? ?? 'User',
      avatarUrl: json['avatar_url'] as String?,
      authType: json['auth_type'] as String? ?? 'oauth',
    );
  }
}

final currentUserProvider = StateProvider<UserModel?>((ref) => null);
final authLoadingProvider = StateProvider<bool>((ref) => false);

final userProfileFutureProvider = FutureProvider.autoDispose<UserModel?>((ref) async {
  final apiKey = ref.watch(apiKeyProvider);
  if (apiKey == null || apiKey.isEmpty) return null;

  try {
    final client = ref.watch(ripClientProvider);
    final data = await client.getCurrentUser();
    final user = UserModel.fromJson(data);
    ref.read(currentUserProvider.notifier).state = user;
    return user;
  } catch (e) {
    log('[userProfileFutureProvider] Failed to fetch current user profile: $e', name: 'AuthProvider');
    return null;
  }
});

class AuthNotifier extends Notifier<void> {
  @override
  void build() {}

  Future<void> loginWithOAuthCode({
    required String provider,
    required String code,
    required String redirectUri,
  }) async {
    ref.read(authLoadingProvider.notifier).state = true;
    try {
      final client = ref.read(ripClientProvider);
      final resp = await client.exchangeOAuthCode(
        provider: provider,
        code: code,
        redirectUri: redirectUri,
        deviceInfo: 'RIP Mobile App',
      );

      final apiKey = resp['api_key'] as String;
      final userData = resp['user'] as Map<String, dynamic>?;

      await ref.read(settingsNotifierProvider.notifier).saveApiKey(apiKey);

      if (userData != null) {
        final user = UserModel.fromJson(userData);
        ref.read(currentUserProvider.notifier).state = user;
      }
      log('[AuthNotifier] Successfully logged in with $provider', name: 'AuthProvider');
    } catch (e) {
      log('[AuthNotifier] OAuth login failed: $e', name: 'AuthProvider');
      rethrow;
    } finally {
      ref.read(authLoadingProvider.notifier).state = false;
    }
  }

  Future<void> logout() async {
    ref.read(authLoadingProvider.notifier).state = true;
    try {
      final client = ref.read(ripClientProvider);
      await client.logoutUser();
    } catch (_) {
    } finally {
      await ref.read(settingsNotifierProvider.notifier).saveApiKey(null);
      ref.read(currentUserProvider.notifier).state = null;
      ref.read(authLoadingProvider.notifier).state = false;
      log('[AuthNotifier] User logged out', name: 'AuthProvider');
    }
  }
}

final authNotifierProvider = NotifierProvider<AuthNotifier, void>(AuthNotifier.new);
