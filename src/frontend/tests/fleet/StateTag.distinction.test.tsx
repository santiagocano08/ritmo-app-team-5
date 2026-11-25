import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StateTag } from "../../src/components/fleet/StateTag";

describe("StateTag distinction", () => {
  it("distinguishes bunched, gap and regular by text and style", () => {
    const { rerender } = render(<StateTag state="regular" />);
    const regularText = screen.getByTestId("state-tag").textContent;
    const regularClass = screen.getByTestId("state-tag").className;

    rerender(<StateTag state="bunched" />);
    const bunchedTag = screen.getByTestId("state-tag");
    const bunchedText = bunchedTag.textContent;
    const bunchedClass = bunchedTag.className;
    expect(bunchedTag).toHaveTextContent(/agrupado/i);
    expect(bunchedText).not.toBe(regularText);
    expect(bunchedClass).not.toBe(regularClass);

    rerender(<StateTag state="gap" />);
    const gapTag = screen.getByTestId("state-tag");
    expect(gapTag).toHaveTextContent(/rezagado/i);
    expect(gapTag.textContent).not.toBe(regularText);
    expect(gapTag.className).not.toBe(regularClass);
    expect(gapTag.textContent).not.toBe(bunchedText);
    expect(gapTag.className).not.toBe(bunchedClass);
  });
});
