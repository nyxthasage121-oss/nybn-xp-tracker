import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
  Client,
  Collection,
} from 'discord.js';
import type { ApiClient } from './api';

export type CommandContext = {
  client: BotClient;
  apiClient: ApiClient;
};

export type BotCommand = {
  name: string;
  data: { toJSON: () => unknown };
  execute: (interaction: ChatInputCommandInteraction, ctx: CommandContext) => Promise<void>;
  autocomplete?: (interaction: AutocompleteInteraction, ctx: CommandContext) => Promise<void>;
};

export type BotClient = Client & {
  commands: Collection<string, BotCommand>;
};
