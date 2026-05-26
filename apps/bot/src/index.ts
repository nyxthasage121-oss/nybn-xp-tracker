/**
 * NYbN Tracker Bot — entry point.
 * Minimal Discord.js bot wired to the Flask web app via ApiClient.
 */
import 'dotenv/config';
import { Client, GatewayIntentBits } from 'discord.js';
import { config } from './config';
import { ApiClient } from './api';
import type { BotClient } from './discord';
import { initClientCommandCollection, registerCommands } from './registerCommands';
import { errorToMessage, logEvent } from './logger';

const apiClient = new ApiClient(config.webAppBaseUrl, config.webAppApiToken);

const client = new Client({
  intents: [GatewayIntentBits.Guilds],
}) as BotClient;

initClientCommandCollection(client);

client.once('ready', async () => {
  logEvent('info', 'bot_ready', { userTag: client.user?.tag });
  await registerCommands(client);
});

client.on('interactionCreate', async (interaction) => {
  const baseMeta = {
    interactionId: interaction.id,
    userId: interaction.user?.id,
    guildId: interaction.guildId,
  };

  try {
    if (interaction.isAutocomplete()) {
      const cmd = client.commands.get(interaction.commandName);
      if (!cmd?.autocomplete) return;
      await cmd.autocomplete(interaction, { client, apiClient });
      return;
    }

    if (!interaction.isChatInputCommand()) return;

    const cmd = client.commands.get(interaction.commandName);
    if (!cmd) return;

    logEvent('info', 'command_execute_start', { ...baseMeta, commandName: interaction.commandName });
    await cmd.execute(interaction, { client, apiClient });
    logEvent('info', 'command_execute_done', { ...baseMeta, commandName: interaction.commandName });
  } catch (error) {
    const code = (error as { code?: number }).code;
    // 40060 = interaction was already acknowledged elsewhere
    if (code === 40060) {
      logEvent('warn', 'interaction_acknowledged_elsewhere', { ...baseMeta, code });
      return;
    }

    logEvent('error', 'command_failure', { ...baseMeta, code, error: errorToMessage(error) });

    if (!interaction.isRepliable()) return;

    if (interaction.replied || interaction.deferred) {
      await interaction.followUp({ content: 'Something went wrong.', ephemeral: true });
      return;
    }
    await interaction.reply({ content: 'Something went wrong.', ephemeral: true });
  }
});

client.login(config.botToken);
