import { driver } from "driver.js";
import "driver.js/dist/driver.css";

const TOUR_KEY = "bibliothek-tour-done";

export function hasSeenTour(): boolean {
  return localStorage.getItem(TOUR_KEY) === "1";
}

export function markTourDone(): void {
  localStorage.setItem(TOUR_KEY, "1");
}

// Steps target elements tagged with data-tour, plus a couple of centered intros.
// All targets exist on the Library page in both mobile and desktop layouts.
export function startTour(): void {
  const d = driver({
    showProgress: true,
    allowClose: true,
    nextBtnText: "Next",
    prevBtnText: "Back",
    doneBtnText: "Done",
    onDestroyed: () => markTourDone(),
    steps: [
      {
        popover: {
          title: "Welcome to Bibliothek",
          description:
            "A quick tour of the basics. Press the close button or Esc to skip at any time.",
        },
      },
      {
        element: '[data-tour="search"]',
        popover: {
          title: "Search your library",
          description: "Find any book by title, author, or ISBN.",
        },
      },
      {
        element: '[data-tour="filter"]',
        popover: {
          title: "Filter",
          description: "Narrow down by tag, location, read status, or availability.",
        },
      },
      {
        element: '[data-tour="household"]',
        popover: {
          title: "Your libraries",
          description: "Switch between your households and libraries friends share with you.",
        },
      },
      {
        element: '[data-tour="theme"]',
        popover: {
          title: "Light or dark",
          description: "Toggle the theme whenever you like.",
        },
      },
      {
        popover: {
          title: "Add books",
          description:
            "Use Add to scan a barcode or type an ISBN, and Scan to add a whole stack at once. Enjoy!",
        },
      },
    ],
  });
  d.drive();
}
