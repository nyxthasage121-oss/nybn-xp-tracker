/**
 * /register — links a Discord user to a character and records their cubby channel.
 *
 * The player runs this command from inside their Tickety cubby channel so the
 * bot can capture the channel ID automatically for future notifications.
 */
import { SlashCommandBuilder } from 'discord.js';
import type { AutocompleteInteraction, ChatInputCommandInteraction } from 'discord.js';
import type { CommandContext } from '../discord';
import { errorToMessage, logEvent } from '../logger';

export const name = 'register';

export const data = new SlashCommandBuilder()
  .setName('register')
  .setDescription('Link your Discord account to your character and save your cubby for notifications')
  .addStringOption((o) =>
    o
      .setName('character')
      .setDescription('Your character name')
      .setAutocomplete(true)
      .setRequired(true),
  );

export async function autocomplete(
  interaction: AutocompleteInteraction,
  { apiClient }: CommandContext,
) {
  const focused = interaction.options.getFocused().toLowerCase();
  try {
    const characters = await apiClient.getPlayerCharacters(interaction.user.id);
    const matches = characters
      .filter((c) => c.toLowerCase().includes(focused))
      .slice(0, 25);
    await interaction.respond(matches.map((c) => ({ name: c, value: c })));
  } catch {
    // Autocomplete must always respond — fall back to empty list on error
    await interaction.respond([]);
  }
}

export async function execute(
  interaction: ChatInputCommandInteraction,
  { apiClient }: CommandContext,
) {
  await interaction.deferReply({ ephemeral: true });

  const characterName = interaction.options.getString('character', true);

  try {
    await apiClient.registerPlayer({
      discordId:      interaction.user.id,
      discordName:    interaction.user.username,
      characterName,
      cubbyChannelId: interaction.channelId,
    });

    logEvent('info', 'register_success', {
      discordId:      interaction.user.id,
      characterName,
      cubbyChannelId: interaction.channelId,
    });

    await interaction.editReply({
      content: [
        `✅ Registered! **${characterName}** is now linked to your Discord account.`,
        `This channel has been saved as your cubby — you'll receive notifications here.`,
      ].join('\n'),
    });
  } catch (error) {
    const msg = errorToMessage(error);
    logEvent('warn', 'register_failed', {
      discordId:    interaction.user.id,
      characterName,
      error:        msg,
    });
    await interaction.editReply({ content: `❌ Registration failed: ${msg}` });
  }
}
