import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const setLoop = vi.fn();
const restartPlayback = vi.fn();
vi.mock("@/lib/api", () => ({ setLoop: (l: boolean) => setLoop(l), restartPlayback: () => restartPlayback() }));

import PlaybackControls from "./PlaybackControls";

beforeEach(() => {
  setLoop.mockReset().mockResolvedValue(undefined);
  restartPlayback.mockReset().mockResolvedValue(undefined);
});

describe("PlaybackControls", () => {
  it("offers Stop loop while clips loop, and clicking it turns looping off", async () => {
    render(<PlaybackControls playback={{ loop: true, held: false }} />);
    await userEvent.click(screen.getByRole("button", { name: /stop loop/i }));
    expect(setLoop).toHaveBeenCalledWith(false);
    expect(screen.getByText(/looping/i)).toBeInTheDocument();
  });

  it("offers Loop clips again once looping is off, and says when the clips are held", async () => {
    const { rerender } = render(<PlaybackControls playback={{ loop: false, held: false }} />);
    expect(screen.getByText(/playing once/i)).toBeInTheDocument();
    rerender(<PlaybackControls playback={{ loop: false, held: true }} />);
    expect(screen.getByText(/finished/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /loop clips/i }));
    expect(setLoop).toHaveBeenCalledWith(true);
  });

  it("Restart plays the clips again from the start", async () => {
    render(<PlaybackControls playback={{ loop: false, held: true }} />);
    await userEvent.click(screen.getByRole("button", { name: /restart/i }));
    expect(restartPlayback).toHaveBeenCalledTimes(1);
  });

  it("shows an error instead of failing silently when the backend cannot be reached", async () => {
    setLoop.mockRejectedValue(new Error("down"));
    render(<PlaybackControls playback={{ loop: true, held: false }} />);
    await userEvent.click(screen.getByRole("button", { name: /stop loop/i }));
    expect(await screen.findByText(/could not change playback/i)).toBeInTheDocument();
  });
});
