enum CommandType {
  search,
  explain,
  trace,
  impact,
  architecture,
  metrics,
  onboard,
  dependencies,
  indexRepository,
  projects,
  deadCode,
  unknown,
}

class ParsedCommand {
  final CommandType type;
  final List<String> arguments;

  ParsedCommand({required this.type, this.arguments = const []});
}

class CommandParser {
  static ParsedCommand parse(String input) {
    final trimmed = input.trim();
    if (!trimmed.startsWith('/')) {
      return ParsedCommand(type: CommandType.unknown);
    }

    final parts = trimmed.substring(1).split(' ');
    final commandName = parts.first.toLowerCase();
    final args = parts.skip(1).toList();

    switch (commandName) {
      case 'search':
        return ParsedCommand(type: CommandType.search, arguments: args);
      case 'explain':
        return ParsedCommand(type: CommandType.explain, arguments: args);
      case 'trace':
        return ParsedCommand(type: CommandType.trace, arguments: args);
      case 'impact':
        return ParsedCommand(type: CommandType.impact, arguments: args);
      case 'architecture':
        return ParsedCommand(type: CommandType.architecture, arguments: args);
      case 'metrics':
        return ParsedCommand(type: CommandType.metrics, arguments: args);
      case 'onboard':
        return ParsedCommand(type: CommandType.onboard, arguments: args);
      case 'dependencies':
        return ParsedCommand(type: CommandType.dependencies, arguments: args);
      case 'index':
        return ParsedCommand(type: CommandType.indexRepository, arguments: args);
      case 'projects':
        return ParsedCommand(type: CommandType.projects, arguments: args);
      case 'dead-code':
        return ParsedCommand(type: CommandType.deadCode, arguments: args);
      default:
        return ParsedCommand(type: CommandType.unknown);
    }
  }

  static List<Map<String, dynamic>> getAvailableCommands() {
    return [
      {'name': '/search <query>', 'description': 'Search codebase'},
      {'name': '/explain <topic>', 'description': 'Explain a symbol or concept'},
      {'name': '/trace <symbol>', 'description': 'Trace symbol flow'},
      {'name': '/impact <symbol>', 'description': 'Analyze impact of a change'},
      {'name': '/architecture', 'description': 'Show project architecture'},
      {'name': '/metrics [module]', 'description': 'Show project metrics'},
      {'name': '/onboard', 'description': 'Get onboarding guide'},
      {'name': '/dependencies <file>', 'description': 'Show file dependencies'},
      {'name': '/index <git_url>', 'description': 'Index a git repository'},
      {'name': '/projects', 'description': 'List all projects'},
      {'name': '/dead-code', 'description': 'Find dead code'},
    ];
  }
}
