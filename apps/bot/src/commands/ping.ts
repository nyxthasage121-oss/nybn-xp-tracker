import { SlashCommandBuilder } from 'discord.js';
import type { ChatInputCommandInteraction } from 'discord.js';
import type { CommandContext } from '../discord';

export const data = new SlashCommandBuilder()
  .setName('ping')
  .setDescription('Health check for the bot runtime');

export const name = 'ping';

export async function execute(interaction: ChatInputCommandInteraction, _ctx: CommandContext) {
  await interaction.reply({ content: 'Pong.', ephemeral: true });
}
