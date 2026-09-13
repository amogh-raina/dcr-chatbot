import { useState } from 'react';
import Icon from './Icon';
import SupportChat from './SupportChat';


const navItems = ['SU', 'SU loan', 'SU abroad', 'Disability allowance', 'Foreign citizen', 'Support for parents', 'Other grants', 'Rates', 'Contact'];
const cards = [
  ['Conditions for receiving disability allowance', 'See which conditions you must meet to receive disability allowance.', 'scale'],
  ['How to apply for disability allowance', 'Learn how to apply and what documentation to include.', 'cursor'],
  ['About documentation', 'Your documentation must describe how your disability affects your ability to work alongside study.', 'file'],
  ['How we assess applications', 'Read what we consider when assessing whether you meet the requirements.', 'search'],
  ['Questions and answers', 'Find answers to the most frequently asked questions about disability allowance.', 'help'],
  ['Status of case processing', 'See the current status of applications for disability allowance.', 'clock'],
  ['Contact', 'Find out how to contact us about disability allowance.', 'message'],
  ['Reduced tax-free amount', 'Your tax-free amount is reduced when you receive disability allowance.', 'card'],
];


function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [slide, setSlide] = useState(2);
  const [paused, setPaused] = useState(false);
  return <main>
    <header className="site-header">
      <div className="utility-row">
        <div className="agency-mark" aria-label="Danish Agency for Higher Education and Science"><span className="crown">♕</span><span>Danish Agency for<br />Higher Education and Science</span></div>
        <div className="utility-links"><button className="mysu">mySU</button><a href="#contact">Contact</a><a href="#news">News</a><a href="#questions">Questions and answers</a><button className="icon-button search-button" aria-label="Open search" aria-expanded={searchOpen} onClick={() => setSearchOpen((value) => !value)}><Icon name={searchOpen ? 'close' : 'search'} /></button></div>
        <button className="mobile-menu icon-button" aria-label="Open navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}><Icon name={menuOpen ? 'close' : 'menu'} /></button>
      </div>
      {searchOpen && <form className="search-panel" onSubmit={(event) => event.preventDefault()}><Icon name="search" size={19} /><input autoFocus placeholder="What are you looking for?" aria-label="Search SU" /><button type="submit">Search</button></form>}
      <nav className={`main-nav ${menuOpen ? 'open' : ''}`}>{navItems.map((item) => <a key={item} href={item === 'Disability allowance' ? '#content' : '#'} className={item === 'Disability allowance' ? 'active' : ''}>{item}</a>)}</nav>
    </header>
    <section className="hero-shell" id="content">
      <div className="breadcrumb">You are here: <a href="#top">Front</a> <span>|</span> Disability allowance</div>
      <div className="hero">
        <div className="hero-copy">
          <h1>{slide === 0 ? 'Minimum requirements for your documentation' : slide === 1 ? 'Watch webinar about disability allowance' : 'Disability allowance'}</h1>
          {slide === 2 ? <><p>Disability allowance is for students in:</p><ul><li>higher education</li><li>Danish vocational education (EUD)</li></ul><p>who have a permanent mental or physical disability that makes it virtually impossible to hold a student job.</p></> : <p>{slide === 0 ? 'If you are applying for disability allowance, your documentation must meet some new minimum requirements.' : 'In the webinar we discuss who can apply, how to apply, and documentation requirements.'}</p>}
        </div>
        <div className={`hero-photo slide-${slide}`} aria-label="Students studying outdoors"><div className="photo-overlay">{slide === 0 ? 'Read about the requirements' : slide === 1 ? 'Watch webinar' : ''}</div><div className="slider-controls"><button aria-label={paused ? 'Play slideshow' : 'Pause slideshow'} onClick={() => setPaused((value) => !value)}><Icon name={paused ? 'play' : 'pause'} size={17} /></button>{[0, 1, 2].map((item) => <button key={item} onClick={() => setSlide(item)} className={`dot ${slide === item ? 'current' : ''}`} aria-label={`Show slide ${item + 1}`} />)}</div></div>
      </div>
    </section>
    <section className="card-area"><div className="cards">{cards.map(([title, description, icon]) => <article className="info-card" key={title}><Icon name={icon} size={48} stroke={1.35} /><h2><a href="#questions"><Icon name="chevron" size={20} />{title}</a></h2><p>{description}</p></article>)}</div>
      <div className="knowledge"><div><span className="eyebrow">WORTH KNOWING</span><h2>Reduced tax-free amount</h2><p>When you receive disability allowance, your tax-free amount is reduced. The allowance compensates for the income you could have earned from a student job.</p><p>The reduced amount also gives you an opportunity to test your working ability for a limited period.</p></div><article className="rates"><h2><a href="#rates"><Icon name="chevron" size={20} />Disability allowance rates</a></h2><p>See current and previous years&apos; rates for disability allowance.</p></article></div>
    </section>
    <section className="reform"><h2>Reform of the SU system in higher education</h2><p>New rules have been adopted for SU for higher education and private education.</p><p>The new rules will affect your SU from January 2027 if you start a new higher education on 1 July 2025 or later.</p><p>Get guidance from your educational institution so that you can plan your education and SU in relation to the new SU rules.</p></section>
    <footer id="contact">{[['Practical information', ['Your responsibility', 'Power of attorney', 'Complaint', 'Digital Post', 'Information about you']], ['More information', ['Links', 'About SU', 'Questions and answers', 'Contact', 'Paragraphs']], ['About su.dk', ['Accessibility statement', 'About su.dk', 'Feedback']]].map(([heading, links]) => <div key={heading}><h2>{heading}</h2>{links.map((link) => <a href="#" key={link}><Icon name="chevron" size={17} />{link}</a>)}</div>)}</footer>
    <SupportChat />
  </main>;
}

export default App;
