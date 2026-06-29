import 'package:equatable/equatable.dart';
import '../../domain/enums/message_type.dart';
import 'rip_response.dart';

class Message extends Equatable {
  final String id;
  final String content;
  final bool isUser;
  final MessageType type;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;
  final List<RipResponseBlock>? blocks;
  final bool isLoading;

  const Message({
    required this.id,
    required this.content,
    required this.isUser,
    this.type = MessageType.text,
    required this.timestamp,
    this.metadata,
    this.blocks,
    this.isLoading = false,
  });

  Message copyWith({
    String? id,
    String? content,
    bool? isUser,
    MessageType? type,
    DateTime? timestamp,
    Map<String, dynamic>? metadata,
    List<RipResponseBlock>? blocks,
    bool? isLoading,
  }) {
    return Message(
      id: id ?? this.id,
      content: content ?? this.content,
      isUser: isUser ?? this.isUser,
      type: type ?? this.type,
      timestamp: timestamp ?? this.timestamp,
      metadata: metadata ?? this.metadata,
      blocks: blocks ?? this.blocks,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  @override
  List<Object?> get props => [
        id,
        content,
        isUser,
        type,
        timestamp,
        metadata,
        blocks,
        isLoading,
      ];
}
