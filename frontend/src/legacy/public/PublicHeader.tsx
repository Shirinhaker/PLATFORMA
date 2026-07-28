interface PublicHeaderProps {
  authenticated: boolean;
  title?: string;
  isHome: boolean;
  onHome(): void;
  onLocation(): void;
  onAccount(): void;
  onBack(): void;
}

function HomeIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m3.5 10.8 8.5-7 8.5 7" />
      <path d="M5.8 9.4v10.2h12.4V9.4M9.5 19.6v-6.2h5v6.2" />
    </svg>
  );
}

function LocationIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

function AccountIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c.7-4 3.1-6 7-6s6.3 2 7 6" />
    </svg>
  );
}

function BackIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m15 5-7 7 7 7" />
    </svg>
  );
}

export function PublicHeader({
  authenticated,
  title,
  isHome,
  onHome,
  onLocation,
  onAccount,
  onBack,
}: PublicHeaderProps) {
  return (
    <header className="public-header">
      <div className="public-header__inner">
        <div className="public-header__identity">
          <button
            className="public-header__brand"
            type="button"
            onClick={onHome}
          >
            <span className="public-header__brand-mark" aria-hidden="true">
              K
            </span>
            <span>Koprik</span>
          </button>
          {!isHome ? (
            <button
              className="public-header__back"
              type="button"
              onClick={onBack}
            >
              <BackIcon />
              <span>Orqaga</span>
            </button>
          ) : null}
          {title ? (
            <span className="public-header__title" aria-hidden="true">
              {title}
            </span>
          ) : null}
        </div>

        <nav className="public-header__actions" aria-label="Asosiy menyu">
          <button type="button" onClick={onHome}>
            <HomeIcon />
            <span className="public-header__desktop-label">Bosh sahifa</span>
          </button>
          <button type="button" onClick={onLocation}>
            <LocationIcon />
            <span>Manzil</span>
          </button>
          <button
            className="public-header__account"
            type="button"
            onClick={onAccount}
          >
            <AccountIcon />
            <span>{authenticated ? "Kabinet" : "Kirish"}</span>
          </button>
        </nav>
      </div>
    </header>
  );
}
