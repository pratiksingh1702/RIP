/// RIP Mascot System
/// Ref: base_design.md Section 5
/// Single source of truth for the purple ghost mascot system.
enum RipMascotPose {
  aiAssistant('ai_assistant.png'),
  bugHunter('bug_hunter.png'),
  celebrating('celebrating.png'),
  coding('coding.png'),
  coffeeBreak('coffee_break.png'),
  confused('confused.png'),
  debugging('debugging.png'),
  developerMode('developer_mode.png'),
  error('error.png'),
  excited('excited.png'),
  focused('focused.png'),
  happy('happy.png'),
  idea('idea.png'),
  laughing('laughing.png'),
  listening('listening.png'),
  loading('loading.png'),
  love('love.png'),
  magic('magic.png'),
  meditating('meditating.png'),
  party('party.png'),
  readingDocs('reading_docs.png'),
  reviewing('reviewing.png'),
  robotMode('robot_mode.png'),
  rocket('rocket.png'),
  running('running.png'),
  sad('sad.png'),
  scanning('scanning.png'),
  searching('searching.png'),
  securityShield('security_shield.png'),
  sleeping('sleeping.png'),
  success('success.png'),
  surprised('surprised.png'),
  talking('talking.png'),
  thinking('thinking.png'),
  thumbsDown('thumbs_down.png'),
  thumbsUp('thumbs_up.png'),
  typing('typing.png'),
  warning('warning.png'),
  waving('waving.png'),
  working('working.png');

  final String fileName;
  const RipMascotPose(this.fileName);

  String get assetPath => 'assets/mascot/$fileName';

  /// Resolves mascot pose based on application/screen state.
  static RipMascotPose fromState(String state) {
    switch (state.toLowerCase()) {
      case 'onboarding':
      case 'welcome':
        return RipMascotPose.waving;
      case 'loading':
      case 'running':
      case 'executing':
        return RipMascotPose.loading;
      case 'success':
      case 'completed':
      case 'passed':
        return RipMascotPose.success;
      case 'celebrate':
      case 'done':
        return RipMascotPose.celebrating;
      case 'error':
      case 'failed':
      case 'crash':
        return RipMascotPose.error;
      case 'warning':
      case 'risk':
      case 'security':
        return RipMascotPose.securityShield;
      case 'thinking':
      case 'generating':
        return RipMascotPose.thinking;
      case 'coding':
      case 'typing':
        return RipMascotPose.coding;
      case 'debugging':
        return RipMascotPose.debugging;
      case 'searching':
      case 'scanning':
        return RipMascotPose.searching;
      case 'reviewing':
        return RipMascotPose.reviewing;
      case 'empty':
      case 'idle':
        return RipMascotPose.sleeping;
      case 'confused':
        return RipMascotPose.confused;
      case 'healthy':
        return RipMascotPose.happy;
      default:
        return RipMascotPose.happy;
    }
  }
}
