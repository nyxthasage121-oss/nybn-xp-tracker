/**
 * NYbN Bot — environment config.
 * All env vars are loaded from .env via dotenv.
 */
import 'dotenv/config';

function required(key: string): string {
  const val = process.env[key];
  if (!val) throw new Error(`Missing required env var: ${key}`);
  return val;
}

export const config = {
  // Discord
  botToken:  required('DISCORD_BOT_TOKEN'),
  clientId:  required('DISCORD_CLIENT_ID'),
  /** Set to your server ID for instant guild-scoped commands during dev.
   *  Leave empty to register global commands (up to 1 hour to propagate). */
  guildId:   process.env.DISCORD_GUILD_ID ?? '',

  // Web app API
  webAppBaseUrl:  required('WEB_APP_BASE_URL').replace(/\/$/, ''),
  webAppApiToken: required('WEB_APP_API_TOKEN'),
};
