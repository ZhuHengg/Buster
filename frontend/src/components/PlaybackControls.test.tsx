import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const setPaused = vi.fn();
const restartPlayback = vi.fn();
vi.mock("@/lib/api", () => ({ setPaused: (p: boolean) => setPaused(p), restartPlayback: () => restartPlayback() }));

import PlaybackControls from "./PlaybackControls";

const playing = { loop: true, held: false, paused: false };
const paused = { loop: true, held: false, paused: true };

beforeEach(() => {
  setPaused.mockReset().mockResolvedValue(undefined);
  restartPlayback.mockReset().mockResolvedValue(undefined);
});

describe("PlaybackControls", () => {
  it("offers Pause while the feeds play, and clicking it pauses them", async () => {
    render(<PlaybackControls playback={playing} />);
    await userEvent.click(screen.getByRole("button", { name: /pause/i }));
    expect(setPaused).toHaveBeenCalledWith(true);
  });

  it("offers Resume while paused, and clicking it resumes the feeds", async () => {
    render(<PlaybackControls playback={paused} />);
    expect(screen.getByRole("button", { name: /resume/i })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: /resume/i }));
    expect(setPaused).toHaveBeenCalledWith(false);
  });

  it("Restart plays the clips again from the start", async () => {
    render(<PlaybackControls playback={playing} />);
    await userEvent.click(screen.getByRole("button", { name: /restart/i }));
    expect(restartPlayback).toHaveBeenCalledTimes(1);
  });

  it("shows an error instead of failing silently when the backend cannot be reached", async () => {
    setPaused.mockRejectedValue(new Error("down"));
    render(<PlaybackControls playback={playing} />);
    await userEvent.click(screen.getByRole("button", { name: /pause/i }));
    expect(await screen.findByText(/could not change playback/i)).toBeInTheDocument();
  });
});
