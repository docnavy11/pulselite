export function createStreamingDots(): HTMLElement {
  const dots = document.createElement("div");
  dots.className = "pulse-streaming-dots";
  dots.innerHTML = "<span></span><span></span><span></span>";
  return dots;
}
