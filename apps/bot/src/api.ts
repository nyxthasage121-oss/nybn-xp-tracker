/**
 * NYbN Web App API client.
 * Thin fetch wrapper — all routes talk to the Flask web app via bearer token.
 */

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
  ) {}

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const data = (await res.json()) as T & { error?: string };

    if (!res.ok) {
      throw new Error((data as { error?: string }).error ?? `API error ${res.status}`);
    }

    return data;
  }

  /** Returns character names available for the given player to register. */
  async getPlayerCharacters(discordId: string): Promise<string[]> {
    const data = await this.request<{ characters: string[] }>(
      'GET',
      `/api/player/characters?discord_id=${encodeURIComponent(discordId)}`,
    );
    return data.characters ?? [];
  }

  /** Links a Discord user to a character and stores their cubby channel ID. */
  async registerPlayer(params: {
    discordId: string;
    discordName: string;
    characterName: string;
    cubbyChannelId: string;
  }): Promise<void> {
    await this.request('POST', '/api/player/register', {
      discord_id:       params.discordId,
      discord_name:     params.discordName,
      character_name:   params.characterName,
      cubby_channel_id: params.cubbyChannelId,
    });
  }
}
