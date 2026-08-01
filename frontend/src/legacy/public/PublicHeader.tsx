interface PublicHeaderProps {
  authenticated: boolean;
  cartCount?: number;
  features?: { listings: boolean; taxi: boolean };
  theme?: "light" | "dark";
  title?: string;
  isHome: boolean;
  onHome(): void;
  onLocation(): void;
  onAccount(): void;
  onBack(): void;
  onListings?: () => void;
  onCart?: () => void;
  onTaxi?: () => void;
  onToggleTheme?: () => void;
}


const noop = () => undefined;


function LocationIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z" />
      <circle cx="12" cy="10" r="2.4" />
    </svg>
  );
}


function CartIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="9" cy="20" r="1.4" />
      <circle cx="18" cy="20" r="1.4" />
      <path d="M2 3h3l2.4 12.5a1.6 1.6 0 0 0 1.6 1.3h8.6a1.6 1.6 0 0 0 1.6-1.3L23 7H6" />
    </svg>
  );
}


function AccountIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
    </svg>
  );
}


function BackIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}


function ThemeIcon({ theme }: { theme: "light" | "dark" }) {
  if (theme === "dark") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="4.5" />
        <path d="M12 1.5v2.5M12 20v2.5M4.2 4.2l1.8 1.8M18 18l1.8 1.8M1.5 12h2.5M20 12h2.5M4.2 19.8l1.8-1.8M18 6l1.8-1.8" />
      </svg>
    );
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z" />
    </svg>
  );
}


export function PublicHeader({
  authenticated: _authenticated,
  cartCount = 0,
  features = { listings: false, taxi: false },
  theme = "light",
  title,
  isHome,
  onHome,
  onLocation,
  onAccount,
  onBack,
  onListings,
  onCart,
  onTaxi,
  onToggleTheme = noop,
}: PublicHeaderProps) {
  return (
    <header className="topbar">
      {isHome ? (
        <div className="tb-home" id="tbHome">
          <button
            aria-label="Koprik bosh sahifasi"
            className="web-brand"
            id="webBrandBtn"
            type="button"
            onClick={onHome}
          >
            Koprik
          </button>
          <nav className="web-nav" aria-label="Asosiy menyu">
            {features.listings && onListings ? (
              <button id="webListingsBtn" type="button" onClick={onListings}>
                E’lonlar
              </button>
            ) : null}
          </nav>
          <button
            aria-label="Manzilim"
            className="icon-btn"
            id="locBtn"
            type="button"
            onClick={onLocation}
          >
            <LocationIcon />
            <span className="web-header-label">Manzil</span>
          </button>
          {onCart ? (
            <button
              aria-label="Savat"
              className="icon-btn"
              id="cartBtn"
              type="button"
              onClick={onCart}
            >
              <CartIcon />
              {cartCount > 0 ? <span className="badge">{cartCount}</span> : null}
              <span className="web-header-label">Savat</span>
            </button>
          ) : null}
          {features.taxi && onTaxi ? (
            <button
              aria-label="Taxi bo'limi"
              className="icon-btn"
              id="taxiCabBtn"
              type="button"
              onClick={onTaxi}
            >
              🚖<span className="web-header-label">Taxi</span>
            </button>
          ) : null}
          <button
            aria-label="Rang rejimini almashtirish"
            className="icon-btn web-only toggle"
            id="desktopThemeBtn"
            type="button"
            onClick={onToggleTheme}
          >
            <ThemeIcon theme={theme} />
          </button>
          <button
            aria-label="Kabinet"
            className="icon-btn"
            id="cabBtn"
            type="button"
            onClick={onAccount}
          >
            <AccountIcon />
            <span className="web-header-label">Kabinet</span>
          </button>
        </div>
      ) : (
        <div className="tb-sub" id="tbSub">
          <button
            aria-label="Orqaga"
            className="back-btn"
            id="backBtn"
            type="button"
            onClick={onBack}
          >
            <BackIcon />
          </button>
          <div className="tb-title" id="tbTitle">{title || "Sahifa"}</div>
        </div>
      )}
    </header>
  );
}
