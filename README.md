# Take-home assignment: Build a simple motor pricing engine

Axis Capital - Henry Hughes



## 0. Setting up the project

I have used python for this project with uv as a package and project management tool to install dependencies and run commands. I have listed installation instructions for uv below. If this is blocked by a corporate firewall use the base python setup just below*

Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On macOS, Homebrew works as well:

```bash
brew install uv
```

From the repository root, install the project and run it:

```bash
uv sync
uv run motor-pricing
uv run pytest
uv run jupyter lab notebooks/pricing_demo.ipynb
```

`uv sync` creates the virtual environment and installs the lockfile. `uv run` uses that environment, so the commands above do not need a separate activation step.

### Python*

The same project can be run with the standard library `venv` and `pip`. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install pytest jupyter ipykernel
motor-pricing
pytest
jupyter lab notebooks/pricing_demo.ipynb
```




## 1. Defining the customers

- Driver A is older and would sit in a minimum of an age/experience curve when it comes to accidents rate. Driver B is in probably the highest risk age/experience group, which would have a significantly higher accident rate.
- City vs urban has a few factors which could also increase the frequency for a car insured in a city. These include busier roads with higher traffic, tighter roads and parking, both of which can increase minor damage frequency. Increased chance of vandalism and theft.
- Although the types of crash in rural areas may actually have a large severity in the claim as the city can be more low speed collisions and rural can have more single-vehicle accidents which can be more serious.
- Howerver, in defining the average claim severity, we can assume that the sports car is more valuable so claims on it will on average be of a greater amount.

For these reasons I have gone with the following rates and claim amounts:

| Driver | Age | Experience | Car type | Area  | Lambda | Severity (CHF) |
| ------ | --- | ---------- | -------- | ----- | ------ | -------------- |
| A      | 45  | 15         | family   | rural | 0.1    | 5000           |
| B      | 22  | 3          | sport    | city  | 0.2    | 10000          |

This can be summarised as I expect a claim from driver A once every 10 years, and from driver B every 5 years.

In practice, I would use a matrix of cummulative risk factors to derive a final lambda.


## 2. Building the pricing model

- Where N~Poisson(lambda)
- The expectation of N is E[N]=lambda
- The expectation of the annual claims cost will be: E[N]*severity

I used a 20% expense loading and 10% risk/profit loading.

- Expense loading:
    - Covers running costs per policy like systems and IT, administration and issuance as well as aquisitions costs.
    - Kept relatively low here as assuming general car insurance with heavily automated systems with low or no broker fees.

- Risk/profit loading:
    - Provides a buffer against uncertainty. For example, if the assumed parameters are incorrect or there is strong year to year volatility.
    - Also includes a profit loading as shareholders expect to make return on capital.

Using this we can calculate the following annual premiums for each of the policyholders.

| Driver | Age | Experience | Car type   | Area  | Lambda | Severity (CHF) | Expected claims | Premium |
| ------ | --- | ---------- | ---------- | ----- | ------ | -------------- | --------------- | ------- |
| A      | 45  | 15         | family car | rural | 0.1    | 5000           | 500             | 660     |
| B      | 22  | 3          | sport car  | city  | 0.2    | 10000          | 2000            | 2640    |

 Currency in CHF



## 3. Building the pricing model

Monte Carlo: 10000 policy-years per driver
seed: 20261125

- Claim counts are Poisson.
- Each claim cost is lognormal with the driver's mean severity.
- The coefficient of variation is 1, so the standard deviation of one claim equals that mean.
- The inputs do not give sigma, and this choice fixes it: sigma = sqrt(log(2)) and mu = log(severity) - sigma^2/2.

The Monte Carlo simulation:
- Each policy-year draws a claim count, then a cost for every claim, and adds those costs.
- A year with no claims costs zero. The mean is the average of the 10,000 yearly totals.
- The median, 90th percentile and 99th percentile are those points on the same totals.
- P(no claims) is the share of years with a zero count.
- P(loss > premium) is the share whose total exceeds the premium.


| Driver | Mean annual loss | Median | 90th percentile | 99th percentile | P(no claims) | P(loss > premium) |
| ------ | ---------------- | ------ | --------------- | --------------- | ------------ | ----------------- |
| A      | 497.03           | 0      | 0               | 10616.99        | 0.9032       | 0.0950            |
| B      | 2059.28          | 0      | 7059.37         | 30602.60        | 0.8170       | 0.1634            |

Question: "Driver A costs us CHF 800 on average, so if we charge CHF 1,000 we cannot lose money."

This statement is incorrect, the CHF 800 average cost is an average over many years not neccessarily what they will cost in any particular year.

For driver A the premium is CHF 660 and the mean annual loss is CHF 497. On average the premium covers the claims, but that average is not what happens in a given year. About 90% of years have no claim at all, while a bad year, the 99th percentile, costs about CHF 10,617. A book of many such policies can still be profitable in total. An individual year can lose money, so a price above the average does not mean a loss is impossible.


## 4. Production readiness

I have eight tests in `tests/test_validation.py`. They are numbered in the same order as the comments.

1. checking a simple case by hand. A claim rate of 0.1 and an average claim of CHF 8,000, with the 20% expense loading and 10% risk loading from above, should give an expected cost of CHF 800 and a premium of 800 x 1.2 x 1.1.
2. If the claim rate is zero there is nothing to charge for. The expected cost and the premium are both zero, and none of the simulated years have a claim.
3. I then simulate 100,000 years of that same driver with the seed held fixed. The average loss should sit within three standard errors of CHF 800, so the simulation is doing what the formula says.
4. With a claim rate of 0.1, about 90.5% of years should have no claim. That is e to the power of -0.1. Over those 100,000 years the simulation should get close to that.
5. Using the same seed twice should give the same years back. A different seed should give different years. That way a run can be repeated and checked later.
6. A negative claim rate, a claim size of zero, or a missing number should raise an error. I would rather the run stop than print a price that is wrong.
7. A loading of -100% or lower is not allowed. The premium is multiplied by (1 + loading), and that has to stay positive, otherwise the price would be zero or negative.
8. Driver B claims more often than driver A, and each of B's claims costs more, so B's premium should be higher.

