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
  workflow,
  agent,
  unknown,
}

class ParsedCommand {
  final CommandType type;
  final List<String> arguments;
  final Map<String, String?> flags;

  ParsedCommand({
    required this.type,
    this.arguments = const [],
    this.flags = const {},
  });

  bool hasFlag(String name) {
    return flags.containsKey(name);
  }

  String? flagValue(String name) {
    return flags[name];
  }
}

class CommandParser {
  static const Set<String> _valueFlags = {
    'level',
    'provider',
    'model',
    'project',
    'max-hops',
    'limit',
    'language',
    'service',
    'format',
    'branch',
    'folder',
    'folder-name',
    'project-name',
    'subdir',
    'subdirectory',
  };

  static const Map<String, String> _flagAliases = {
    'd': 'diagram',
    't': 'tree',
    'deps': 'dependencies',
  };

  static ParsedCommand parse(String input) {
    final trimmed = input.trim();
    if (!trimmed.startsWith('/')) {
      return ParsedCommand(type: CommandType.unknown);
    }

    final parts = trimmed
        .substring(1)
        .split(RegExp(r'\s+'))
        .where((p) => p.isNotEmpty)
        .toList();
    if (parts.isEmpty) {
      return ParsedCommand(type: CommandType.unknown);
    }
    final commandName = parts.first.toLowerCase();
    final parsed = _parseArgsAndFlags(parts.skip(1).toList());
    final args = parsed.arguments;
    final flags = parsed.flags;

    switch (commandName) {
      case 'search':
        return ParsedCommand(
            type: CommandType.search, arguments: args, flags: flags);
      case 'explain':
        return ParsedCommand(
            type: CommandType.explain, arguments: args, flags: flags);
      case 'trace':
        return ParsedCommand(
            type: CommandType.trace, arguments: args, flags: flags);
      case 'impact':
        return ParsedCommand(
            type: CommandType.impact, arguments: args, flags: flags);
      case 'architecture':
        return ParsedCommand(
            type: CommandType.architecture, arguments: args, flags: flags);
      case 'metrics':
        return ParsedCommand(
            type: CommandType.metrics, arguments: args, flags: flags);
      case 'onboard':
        return ParsedCommand(
            type: CommandType.onboard, arguments: args, flags: flags);
      case 'dependencies':
        return ParsedCommand(
            type: CommandType.dependencies, arguments: args, flags: flags);
      case 'index':
        return ParsedCommand(
            type: CommandType.indexRepository, arguments: args, flags: flags);
      case 'projects':
        return ParsedCommand(
            type: CommandType.projects, arguments: args, flags: flags);
      case 'dead-code':
        return ParsedCommand(
            type: CommandType.deadCode, arguments: args, flags: flags);
      case 'workflow':
        return ParsedCommand(type: CommandType.workflow, arguments: args, flags: flags);
      case 'agent':
        return ParsedCommand(type: CommandType.agent, arguments: args, flags: flags);
      default:
        return ParsedCommand(type: CommandType.unknown);
    }
  }

  static _ParsedParts _parseArgsAndFlags(List<String> tokens) {
    final args = <String>[];
    final flags = <String, String?>{};

    for (var i = 0; i < tokens.length; i++) {
      final token = tokens[i];
      if (!token.startsWith('-') || token == '-') {
        args.add(token);
        continue;
      }

      var flagToken = token.replaceFirst(RegExp(r'^--?'), '');
      String? value;
      if (flagToken.contains('=')) {
        final pieces = flagToken.split('=');
        flagToken = pieces.first;
        value = pieces.skip(1).join('=');
      }

      final name = _flagAliases[flagToken] ?? flagToken;
      if (value == null && _valueFlags.contains(name)) {
        final hasNext = i + 1 < tokens.length;
        if (hasNext && !tokens[i + 1].startsWith('-')) {
          value = tokens[i + 1];
          i++;
        }
      }
      flags[name] = value ?? 'true';
    }

    return _ParsedParts(arguments: args, flags: flags);
  }

  static List<Map<String, dynamic>> getAvailableCommands() {
    return [
      {
        'name': '/search <query>',
        'description': 'Search codebase',
        'flags': [
          {'name': '--limit', 'description': 'Result count', 'value': '<n>'},
          {
            'name': '--language',
            'description': 'Language filter',
            'value': '<lang>'
          },
          {
            'name': '--service',
            'description': 'Service filter',
            'value': '<name>'
          },
        ],
      },
      {
        'name': '/explain <topic>',
        'description': 'Explain a symbol or concept',
        'flags': [
          {
            'name': '--level',
            'description': 'Context scope',
            'value': '<file|class|function>'
          },
          {'name': '--diagram', 'description': 'Mermaid workflow'},
          {'name': '--tree', 'description': 'Workflow tree'},
          {'name': '--deps', 'description': 'Dependency table'},
          {'name': '--code', 'description': 'Relevant code'},
          {'name': '--no-llm', 'description': 'Graph only'},
          {'name': '--max-hops', 'description': 'Trace depth', 'value': '<n>'},
          {
            'name': '--provider',
            'description': 'LLM provider',
            'value': '<name>'
          },
          {'name': '--model', 'description': 'LLM model', 'value': '<name>'},
        ],
      },
      {'name': '/trace <symbol>', 'description': 'Trace symbol flow'},
      {'name': '/impact <symbol>', 'description': 'Analyze impact of a change'},
      {'name': '/architecture', 'description': 'Show project architecture'},
      {'name': '/metrics [module]', 'description': 'Show project metrics'},
      {'name': '/onboard', 'description': 'Get onboarding guide'},
      {'name': '/dependencies <file>', 'description': 'Show file dependencies'},
      {
        'name': '/index <git_url> --folder <name> --subdir lib',
        'description': 'Index a git repository',
        'flags': [
          {
            'name': '--folder',
            'description': 'Clone folder',
            'value': '<name>'
          },
          {
            'name': '--subdir',
            'description': 'Index subfolder',
            'value': '<path>'
          },
          {
            'name': '--project-name',
            'description': 'Project label',
            'value': '<name>'
          },
          {'name': '--branch', 'description': 'Git branch', 'value': '<name>'},
        ],
      },
      {'name': '/projects', 'description': 'List all projects'},
      {'name': '/dead-code', 'description': 'Find dead code'},
      {
        'name': '/workflow',
        'description': 'Attach and run a workflow from this chat message'
      },
            {
        'name': '/agent <task>',
        'description': 'Run autonomous agent for engineering tasks',
        'flags': [
          {'name': '--model', 'description': 'LLM model preference', 'value': '<name>'},
        ],
      },
    ];
  }
}

class _ParsedParts {
  final List<String> arguments;
  final Map<String, String?> flags;

  const _ParsedParts({required this.arguments, required this.flags});
}

