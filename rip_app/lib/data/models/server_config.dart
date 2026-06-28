import 'package:equatable/equatable.dart';

class ServerConfig extends Equatable {
  final String serverUrl;
  final String? apiKey;

  const ServerConfig({
    required this.serverUrl,
    this.apiKey,
  });

  ServerConfig copyWith({
    String? serverUrl,
    String? apiKey,
  }) {
    return ServerConfig(
      serverUrl: serverUrl ?? this.serverUrl,
      apiKey: apiKey ?? this.apiKey,
    );
  }

  @override
  List<Object?> get props => [serverUrl, apiKey];
}
