import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataStateBanner } from "../../src/components/shell/DataStateBanner";

describe("DataStateBanner", () => {
  it("is hidden for the live state", () => {
    const { container } = render(<DataStateBanner status="live" sourcesDown={[]} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it("shows an alert for the estimated state mentioning a source is down", () => {
    render(
      <DataStateBanner
        status="estimated"
        sourcesDown={[{ bus_id: "B-103", since: "2026-11-24T08:01:30Z" }]}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/estimad/i);
    expect(alert).toHaveTextContent(/fuente/i);
  });

  it("shows a no_data alert telling the dispatcher to rely on the day's plan", () => {
    render(<DataStateBanner status="no_data" sourcesDown={[]} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/plan del día/i);
  });
});
